"""fastvex services package.

Public API is re-exported here so callers can continue to use::

    from fastvex.services import plan_deploy, deploy_slots, ...

Internal implementation lives in the private sub-modules:
  _project.py  – init / show / validate / history / toolchain
  _deploy.py   – plan_deploy / deploy_slots
  _migrate.py  – migrate_project
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..models import Config, PROGRAM_NAME_LIMIT, ResolvedSlot, merge_build_args, resolve_slot, utc_now_iso
from ..project import ProjectPaths
from ..state_model import ExecutionRecord, Settings, State
from ..errors import ValidationError
from ..storage import (
    default_settings,
    default_state,
    load_state,
    save_state,
)


# ---------------------------------------------------------------------------
# Report / Request data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InitReport:
    paths: ProjectPaths
    config_created: bool
    state_created: bool
    settings_created: bool
    gitignore_created: bool
    config_exists: bool
    state_exists: bool
    settings_exists: bool
    gitignore_exists: bool
    legacy_config_exists: bool


@dataclass(frozen=True)
class ShowReport:
    paths: ProjectPaths
    config: Config
    state: State


@dataclass(frozen=True)
class ValidationReport:
    paths: ProjectPaths
    warnings: list[str]


@dataclass(frozen=True)
class HistoryReport:
    paths: ProjectPaths
    state: State


@dataclass(frozen=True)
class HistoryCleanReport:
    paths: ProjectPaths
    removed_count: int
    kept_count: int
    state: State


@dataclass(frozen=True)
class DeployRequest:
    slots: str | None = None
    group: str | None = None
    port: str | None = None
    clean: bool = False
    quiet: bool = False
    dry_run: bool = False
    yes: bool = False


@dataclass(frozen=True)
class DeployPlan:
    paths: ProjectPaths
    config: Config
    state: State
    settings: Settings
    requested_slots: list[int]
    deploy_slots: list[ResolvedSlot]
    skipped_empty_slots: list[int]
    warnings: list[str]
    port: str
    indirect: bool


@dataclass(frozen=True)
class DeployReport:
    paths: ProjectPaths
    config: Config
    slots: list[int]
    execution: ExecutionRecord | None
    failed_slots: list[int]
    aborted: bool = False


@dataclass(frozen=True)
class ToolchainReport:
    pros_path: str
    rediscovered: bool


@dataclass(frozen=True)
class MigrateReport:
    source: Path
    output: Path
    wrote_in_place: bool
    warnings: list[str]


# ---------------------------------------------------------------------------
# Internal utilities (used by sub-modules)
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    return utc_now_iso().replace("-", "").replace(":", "").split("+", 1)[0].replace("T", "-")


def _backup(path: Path, *, tag: str = "backup") -> None:
    if not path.exists():
        return
    suffix = "".join(path.suffixes)
    stem = path.name.removesuffix(suffix) if suffix else path.name
    backup = path.with_name(f"{stem}.{tag}.{_timestamp()}{suffix}")
    shutil.copy2(path, backup)


def _backup_v1(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(f"{path.stem}.v1.backup.{_timestamp()}{path.suffix}")
    shutil.copy2(path, backup)


def _recover_interrupted_execution(state: State) -> bool:
    execution = state.active_execution
    if execution is None or execution.status != "running":
        return False

    ended_at = utc_now_iso()
    execution.status = "interrupted"
    execution.ended_at = ended_at
    state.active_execution = None
    state.updated_at = ended_at
    history = list(state.history)
    history.append(execution)
    state.history = history[-default_settings().history_retention_count:]
    return True


def _load_state_resilient(path: Path) -> State:
    try:
        state = load_state(path)
    except ValidationError:
        _backup(path, tag="corrupt")
        state = default_state()
        save_state(path, state)
        return state
    if _recover_interrupted_execution(state):
        save_state(path, state)
    return state


# ---------------------------------------------------------------------------
# Public validation helpers
# ---------------------------------------------------------------------------

def parse_slot_expr(expr: str) -> tuple[list[int], list[str]]:
    values: list[int] = []
    warnings: list[str] = []
    seen: set[int] = set()
    for token in expr.replace(",", " ").split():
        slot = int(token)
        if slot < 1 or slot > 8:
            raise ValidationError(f"slot out of range: {slot}")
        if slot in seen:
            warnings.append(f"duplicate slot ignored: {slot}")
            continue
        seen.add(slot)
        values.append(slot)
    return values, warnings


def validate_config(config: Config) -> list[str]:
    warnings: list[str] = []
    for profile_key, profile in config.profiles.items():
        if not profile.build_args:
            warnings.append(f"profile '{profile_key}' has empty buildArgs")

    for alliance_key, alliance in config.alliances.items():
        for route_key, route in alliance.routes.items():
            if not route.build_args:
                warnings.append(f"route '{alliance_key}:{route_key}' has empty buildArgs")

    seen_pairs: dict[tuple[str, str], int] = {}
    for slot in range(1, 9):
        resolved = resolve_slot(config, slot)
        if resolved is None:
            continue
        profile = config.profiles[resolved.profile]
        route = config.alliances[profile.alliance].routes[resolved.route]
        _, merge_warnings = merge_build_args(profile.build_args, route.build_args)
        warnings.extend(f"slot {slot}: {warning}" for warning in merge_warnings)
        if len(resolved.program_name) > PROGRAM_NAME_LIMIT:
            warnings.append(
                f"slot {slot} programName '{resolved.program_name}' exceeds {PROGRAM_NAME_LIMIT} chars"
            )
        pair = (resolved.profile, resolved.route)
        if pair in seen_pairs:
            warnings.append(
                f"slot {slot} duplicates profile+route from slot {seen_pairs[pair]}: "
                f"{resolved.profile}:{resolved.route}"
            )
        else:
            seen_pairs[pair] = slot

    all_group = config.slot_groups.get("all")
    if all_group != list(range(1, 9)):
        warnings.append("slotGroups.all is missing or not complete 1..8")

    return warnings


# ---------------------------------------------------------------------------
# Re-exports from sub-modules
# ---------------------------------------------------------------------------

from ._project import (  # noqa: E402
    init_project,
    show_project,
    validate_project,
    get_history,
    clean_history,
    show_toolchain,
)
from ._deploy import plan_deploy, deploy_slots  # noqa: E402
from ._migrate import migrate_project  # noqa: E402

__all__ = [
    # data classes
    "InitReport",
    "ShowReport",
    "ValidationReport",
    "HistoryReport",
    "HistoryCleanReport",
    "DeployRequest",
    "DeployPlan",
    "DeployReport",
    "ToolchainReport",
    "MigrateReport",
    # validation helpers
    "parse_slot_expr",
    "validate_config",
    # commands
    "init_project",
    "show_project",
    "validate_project",
    "get_history",
    "clean_history",
    "show_toolchain",
    "plan_deploy",
    "deploy_slots",
    "migrate_project",
]
