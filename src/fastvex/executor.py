from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Config, Profile, mode_to_camel, resolve_profile, to_state_slot_entry, utc_now_iso
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


def _last_uploaded_profile_id(state: dict[str, Any]) -> str | None:
    """Return the profileId of the most recent successful upload across all slots."""
    for execution in reversed(state.get("history", [])):
        for result in reversed(execution.get("results", [])):
            if result.get("upload", {}).get("ok"):
                profile_id = result.get("profileId")
                if isinstance(profile_id, str) and profile_id:
                    return profile_id
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
    def run(self, args: list[str], cwd: Path, quiet: bool) -> CommandResult:
        resolved_args = list(args)
        resolved_args[0] = _resolve_executable(resolved_args[0])
        proc = subprocess.run(
            resolved_args,
            cwd=str(cwd),
            text=True,
            capture_output=quiet,
            check=False,
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
) -> tuple[bool, str, float]:
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
    for idx, cmd in enumerate(candidates):
        result = runner.run(cmd, project_root, quiet)
        if result.returncode == 0:
            return True, "", round(time.perf_counter() - started, 2)
        name = " ".join(cmd[:2]) if len(cmd) >= 2 else cmd[0]
        detail = result.output or f"{name} failed with code {result.returncode}"
        errors.append(f"[{idx + 1}/{len(candidates)}] {name} failed:\n{detail}")

    return False, "\n\n".join(errors), round(time.perf_counter() - started, 2)


def execute_upload(
    project_root: Path,
    config: Config,
    state: dict[str, Any],
    options: RunOptions,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    runner = runner or SubprocessRunner()
    start_ts = utc_now_iso()
    started = time.perf_counter()

    before_slots = dict(state.get("currentSlots", {}))
    results: list[dict[str, Any]] = []
    current_slots = dict(before_slots)
    last_uploaded_profile_id = _last_uploaded_profile_id(state)

    touch_files = find_compile_time_dependent_sources(project_root)

    for slot in options.slots:
        profile = resolve_profile(config, slot)
        final_name = render_final_name(config, profile, options.robot_name)

        slot_result = {
            "slot": slot,
            "profileId": profile.profile_id,
            "roleId": profile.role_id,
            "routeSet": profile.route_set,
            "routeKey": profile.route_key,
            "mode": profile.mode,
            "route": profile.route,
            "finalName": final_name,
            "build": {"ok": False, "durationSec": 0.0, "error": ""},
            "upload": {"ok": False, "durationSec": 0.0, "error": ""},
        }

        if options.dry_run:
            slot_result["build"]["ok"] = True
            slot_result["upload"]["ok"] = True
            slot_result["dryRun"] = True
            results.append(slot_result)
            continue

        profile_switched = (
            last_uploaded_profile_id is not None
            and last_uploaded_profile_id != profile.profile_id
        )

        # Build output depends on profile, not slot.
        if profile_switched:
            for touch_path in touch_files:
                touch_path.touch()

        if options.clean:
            result = runner.run(["make", "clean"], project_root, options.quiet)
            if result.returncode != 0:
                slot_result["build"]["error"] = result.output or "make clean failed"
                results.append(slot_result)
                continue

        ok, err_text, spent = run_build(project_root, profile, options.quiet, runner)
        slot_result["build"]["durationSec"] = spent
        if not ok:
            slot_result["build"]["error"] = err_text or "build failed"
            results.append(slot_result)
            continue
        slot_result["build"]["ok"] = True

        upload_args = ["pros", "upload", "--slot", str(slot), "--name", final_name]
        if options.port:
            upload_args.extend(["--port", options.port])

        t1 = time.perf_counter()
        result = runner.run(upload_args, project_root, options.quiet)
        slot_result["upload"]["durationSec"] = round(time.perf_counter() - t1, 2)
        if result.returncode != 0:
            slot_result["upload"]["error"] = result.output or "upload failed"
            results.append(slot_result)
            continue
        slot_result["upload"]["ok"] = True
        last_uploaded_profile_id = profile.profile_id

        now = utc_now_iso()
        current_slots[str(slot)] = to_state_slot_entry(profile, final_name, now)
        results.append(slot_result)

    all_ok = all(r["build"]["ok"] and r["upload"]["ok"] for r in results) if results else True
    any_ok = any(r["build"]["ok"] and r["upload"]["ok"] for r in results)
    status = "success" if all_ok else ("partial" if any_ok else "failed")

    end_ts = utc_now_iso()
    execution = {
        "startedAt": start_ts,
        "endedAt": end_ts,
        "status": status,
        "robotName": options.robot_name,
        "port": options.port,
        "requestedSlots": options.slots,
        "beforeSnapshot": before_slots,
        "afterSnapshot": current_slots,
        "results": results,
        "durationSec": round(time.perf_counter() - started, 2),
        "dryRun": options.dry_run,
        "username": get_git_username(),
        "hostname": get_hostname(),
    }

    state["currentSlots"] = current_slots
    state["updatedAt"] = end_ts
    if not state.get("createdAt"):
        state["createdAt"] = start_ts
    state["lastRobotName"] = options.robot_name
    state["lastPort"] = options.port

    history = list(state.get("history", []))
    history.append(execution)
    state["history"] = history[-config.history_retention_count:]

    return execution
