from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .models import Config, Profile, mode_to_camel, resolve_profile, utc_now_iso
from .state_model import ExecutionRecord, SlotExecutionResult, State, StateSlotEntry, StepRecord
from .storage import get_git_username, get_hostname


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


def _last_built_profile_id(state: State) -> str | None:
    """Return the profileId of the most recent successful build."""
    for execution in reversed(state.history):
        for result in reversed(execution.results):
            if result.build.ok and result.profile_id:
                return result.profile_id
    return None


@dataclass
class CommandResult:
    returncode: int
    output: str = ""


class CommandRunner:
    def run(self, args: list[str], cwd: Path, quiet: bool) -> CommandResult:
        raise NotImplementedError


def _resolve_executable(command: str) -> str:
    command_path = Path(command)
    if command_path.parent != Path(".") or command_path.suffix:
        return command

    extensions = [""]
    if os.name == "nt":
        extensions = [".cmd", ".bat", ".exe", ".com", ""]

    for directory in os.environ.get("PATH", "").split(os.pathsep):
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
        resolved_args = list(args)
        resolved_args[0] = _resolve_executable(resolved_args[0])
        env = {**os.environ, **self._toolchain_env} if self._toolchain_env else None
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
    robot_name: str
    port: str
    clean: bool
    quiet: bool
    dry_run: bool
    yes: bool


def render_final_name(config: Config, profile: Profile, robot_name: str) -> str:
    route_suffix = f"-{profile.route_name}" if profile.route > 0 and profile.route_name else ""
    mode_camel = mode_to_camel(profile.mode)
    return config.defaults.name_template.format(
        modeCamel=mode_camel,
        routeSuffix=route_suffix,
        robotName=robot_name,
    )


def run_build(
    project_root: Path,
    profile: Profile,
    quiet: bool,
    runner: CommandRunner,
) -> StepRecord:
    common_suffix = [
        f"MODE={profile.mode}",
        f"ROUTE={profile.route}",
    ]

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
        if result.returncode == 0:
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


def execute_upload(
    project_root: Path,
    config: Config,
    state: State,
    options: RunOptions,
    runner: CommandRunner | None = None,
    toolchain_env: dict[str, str] | None = None,
) -> ExecutionRecord:
    runner = runner or SubprocessRunner(toolchain_env=toolchain_env)
    start_ts = utc_now_iso()
    started = time.perf_counter()

    before_slots = dict(state.current_slots)
    results: list[SlotExecutionResult] = []
    current_slots = dict(before_slots)
    last_built_profile_id = _last_built_profile_id(state)

    touch_files = find_compile_time_dependent_sources(project_root)

    for slot in options.slots:
        profile = resolve_profile(config, slot)
        final_name = render_final_name(config, profile, options.robot_name)

        slot_result = SlotExecutionResult(
            slot=slot,
            profile_id=profile.profile_id,
            role_id=profile.role_id,
            route_set=profile.route_set,
            route_key=profile.route_key,
            mode=profile.mode,
            route=profile.route,
            final_name=final_name,
        )

        if options.dry_run:
            slot_result.build.ok = True
            slot_result.upload.ok = True
            slot_result.dry_run = True
            results.append(slot_result)
            continue

        profile_switched = (
            last_built_profile_id is not None
            and last_built_profile_id != profile.profile_id
        )

        # Build output depends on profile, not slot.
        if profile_switched:
            for touch_path in touch_files:
                touch_path.touch()

        if options.clean:
            result = runner.run(["make", "clean"], project_root, options.quiet)
            if result.returncode != 0:
                slot_result.build = StepRecord(
                    ok=False,
                    command=["make", "clean"],
                    returncode=result.returncode,
                    output=result.output,
                    error=result.output or "make clean failed",
                )
                results.append(slot_result)
                continue

        slot_result.build = run_build(project_root, profile, options.quiet, runner)
        if not slot_result.build.ok:
            if not slot_result.build.error:
                slot_result.build.error = "build failed"
            results.append(slot_result)
            continue
        last_built_profile_id = profile.profile_id

        upload_args = ["pros", "upload", "--slot", str(slot), "--name", final_name]
        if options.port:
            upload_args.extend(["--port", options.port])

        t1 = time.perf_counter()
        result = runner.run(upload_args, project_root, options.quiet)
        slot_result.upload = StepRecord(
            ok=result.returncode == 0,
            command=upload_args,
            duration_sec=round(time.perf_counter() - t1, 2),
            returncode=result.returncode,
            output=result.output,
            error="" if result.returncode == 0 else (result.output or "upload failed"),
        )
        if result.returncode != 0:
            results.append(slot_result)
            continue

        now = utc_now_iso()
        current_slots[slot] = StateSlotEntry.from_profile(profile, final_name, now)
        results.append(slot_result)

    all_ok = all(result.build.ok and result.upload.ok for result in results) if results else True
    any_ok = any(result.build.ok and result.upload.ok for result in results)
    status = "success" if all_ok else ("partial" if any_ok else "failed")

    end_ts = utc_now_iso()
    execution = ExecutionRecord(
        started_at=start_ts,
        ended_at=end_ts,
        status=status,
        robot_name=options.robot_name,
        port=options.port,
        requested_slots=options.slots,
        before_snapshot=before_slots,
        after_snapshot=current_slots,
        results=results,
        duration_sec=round(time.perf_counter() - started, 2),
        dry_run=options.dry_run,
        username=get_git_username(),
        hostname=get_hostname(),
    )

    state.current_slots = current_slots
    state.updated_at = end_ts
    if not state.created_at:
        state.created_at = start_ts
    state.last_robot_name = options.robot_name
    state.last_port = options.port

    history = list(state.history)
    history.append(execution)
    state.history = history[-config.history_retention_count:]

    return execution
