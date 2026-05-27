from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .models import utc_now_iso
from .resolve import ResolvedSlot, build_arg_strings
from .state_model import (
    BuildRecord,
    BuildSignature,
    ExecutionRecord,
    State,
    StateSlotEntry,
    StepRecord,
    UploadRecord,
)
from .project import get_git_username, get_hostname


BUILD_CONSTANTS = {
    "kIsRed",
    "kIsBlue",
    "kIsSkill",
    "kIsDebug",
    "kIsCompetition",
    "kRoute",
}


def find_compile_time_dependent_sources(project_root: Path) -> list[Path]:
    src_dir = project_root / "src"
    if not src_dir.exists():
        return []

    matched: list[Path] = []
    for cpp_file in src_dir.rglob("*.cpp"):
        try:
            content = cpp_file.read_text(encoding="utf-8", errors="ignore")
            if any(const in content for const in BUILD_CONSTANTS):
                matched.append(cpp_file)
        except OSError:
            continue
    return matched


@dataclass
class CommandResult:
    returncode: int
    output: str = ""


class CommandRunner:
    def run(self, args: list[str], cwd: Path, quiet: bool) -> CommandResult:
        raise NotImplementedError


def _resolve_executable(command: str, env: dict[str, str] | None = None) -> str:
    command_path = Path(command)
    if command_path.parent != Path(".") or command_path.suffix:
        return command

    extensions = [""]
    if os.name == "nt":
        extensions = [".cmd", ".bat", ".exe", ".com", ""]

    search_env = env if env is not None else os.environ
    for directory in search_env.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        base = Path(directory)
        for extension in extensions:
            candidate = base / f"{command}{extension}"
            if candidate.exists():
                return str(candidate)
    return command


class SubprocessRunner(CommandRunner):
    def __init__(self, toolchain_env: dict[str, str] | None = None) -> None:
        self._toolchain_env = toolchain_env or {}

    def run(self, args: list[str], cwd: Path, quiet: bool) -> CommandResult:
        env = {**os.environ, **self._toolchain_env} if self._toolchain_env else None
        resolved_args = list(args)
        resolved_args[0] = _resolve_executable(resolved_args[0], env=env)
        proc = subprocess.run(
            resolved_args,
            cwd=str(cwd),
            text=True,
            capture_output=quiet,
            check=False,
            env=env,
        )
        out = ""
        if quiet:
            out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return CommandResult(proc.returncode, out)


@dataclass
class RunOptions:
    slots: list[int]
    port: str
    clean: bool
    quiet: bool
    dry_run: bool
    yes: bool


BUILD_FAILURE_MARKERS = (
    "PROS toolchain not found",
    "ERROR WHILE CALLING 'make'",
)


def _build_result_failed(result: CommandResult) -> bool:
    if result.returncode != 0:
        return True
    return any(marker in result.output for marker in BUILD_FAILURE_MARKERS)


def run_build(
    project_root: Path,
    slot: ResolvedSlot,
    quiet: bool,
    runner: CommandRunner,
) -> StepRecord:
    common_suffix = build_arg_strings(slot.build_args)

    candidates = [
        ["pros", "make", *common_suffix],
        ["make", *common_suffix, f"-j{max(1, (os.cpu_count() or 1))}"],
    ]

    errors: list[str] = []
    started = time.perf_counter()
    last_command: list[str] = []
    last_returncode: int | None = None
    last_output = ""
    for idx, cmd in enumerate(candidates):
        result = runner.run(cmd, project_root, quiet)
        last_command = cmd
        last_returncode = result.returncode
        last_output = result.output
        if not _build_result_failed(result):
            return StepRecord(
                ok=True,
                command=cmd,
                duration_sec=round(time.perf_counter() - started, 2),
                returncode=result.returncode,
                output=result.output,
            )
        name = " ".join(cmd[:2]) if len(cmd) >= 2 else cmd[0]
        detail = result.output or f"{name} failed with code {result.returncode}"
        errors.append(f"[{idx + 1}/{len(candidates)}] {name} failed:\n{detail}")

    return StepRecord(
        ok=False,
        command=last_command,
        duration_sec=round(time.perf_counter() - started, 2),
        returncode=last_returncode,
        output=last_output,
        error="\n\n".join(errors),
    )


def execute_deploy(
    project_root: Path,
    deploy_slots: list[ResolvedSlot],
    state: State,
    options: RunOptions,
    runner: CommandRunner | None = None,
    toolchain_env: dict[str, str] | None = None,
    checkpoint: Callable[[ExecutionRecord], None] | None = None,
) -> ExecutionRecord:
    runner = runner or SubprocessRunner(toolchain_env=toolchain_env)
    start_ts = utc_now_iso()
    started = time.perf_counter()
    touch_files = find_compile_time_dependent_sources(project_root)

    builds: list[BuildRecord] = []
    uploads: list[UploadRecord] = []
    built: dict[str, BuildRecord] = {}
    current_slots = dict(state.current_slots)
    execution = ExecutionRecord(
        started_at=start_ts,
        status="running",
        port=options.port,
        requested_slots=options.slots,
        builds=builds,
        uploads=uploads,
        dry_run=options.dry_run,
        username=get_git_username(),
        hostname=get_hostname(),
    )

    def checkpoint_now() -> None:
        execution.builds = builds
        execution.uploads = uploads
        if checkpoint is None:
            return
        checkpoint(execution)

    if not options.dry_run:
        checkpoint_now()

    for slot in deploy_slots:
        signature = BuildSignature.from_slot(slot)
        signature_key = signature.model_dump_json()
        build = built.get(signature_key)

        if build is None:
            build_id = f"build-{len(builds) + 1}"
            build = BuildRecord(id=build_id, signature=signature)
            built[signature_key] = build
            builds.append(build)

            if options.dry_run:
                build.step.ok = True
            else:
                if state.last_build_signature != signature:
                    for touch_path in touch_files:
                        touch_path.touch()
                    state.last_build_signature = None

                if options.clean:
                    clean_result = runner.run(["make", "clean"], project_root, options.quiet)
                    if clean_result.returncode != 0:
                        build.step = StepRecord(
                            ok=False,
                            command=["make", "clean"],
                            returncode=clean_result.returncode,
                            output=clean_result.output,
                            error=clean_result.output or "make clean failed",
                        )
                    else:
                        build.step = run_build(project_root, slot, options.quiet, runner)
                else:
                    build.step = run_build(project_root, slot, options.quiet, runner)

                if build.step.ok:
                    state.last_build_signature = signature
                checkpoint_now()

        upload = UploadRecord(
            slot=slot.slot,
            build_id=build.id,
            program_name=slot.program_name,
        )

        if options.dry_run:
            upload.status = "success"
            upload.step.ok = True
            uploads.append(upload)
            continue

        if not build.step.ok:
            upload.status = "skipped"
            upload.reason = "buildFailed"
            uploads.append(upload)
            checkpoint_now()
            continue

        upload_args = ["pros", "upload", "--slot", str(slot.slot), "--name", slot.program_name]
        if options.port:
            upload_args.extend(["--port", options.port])

        t1 = time.perf_counter()
        result = runner.run(upload_args, project_root, options.quiet)
        upload.step = StepRecord(
            ok=result.returncode == 0,
            command=upload_args,
            duration_sec=round(time.perf_counter() - t1, 2),
            returncode=result.returncode,
            output=result.output,
            error="" if result.returncode == 0 else (result.output or "upload failed"),
        )
        upload.status = "success" if upload.step.ok else "failed"
        if upload.step.ok:
            current_slots[slot.slot] = StateSlotEntry.from_slot(slot, utc_now_iso())
        uploads.append(upload)
        checkpoint_now()

    failures = [
        upload
        for upload in uploads
        if upload.status != "success" or not upload.step.ok
    ]
    all_ok = not failures and all(build.step.ok for build in builds)
    any_ok = any(upload.status == "success" and upload.step.ok for upload in uploads)
    status = "success" if all_ok else ("partial" if any_ok else "failed")

    end_ts = utc_now_iso()
    execution.ended_at = end_ts
    execution.status = status
    execution.duration_sec = round(time.perf_counter() - started, 2)

    if not options.dry_run:
        state.current_slots = current_slots
        state.updated_at = end_ts
        if not state.created_at:
            state.created_at = start_ts
        checkpoint_now()

    return execution
