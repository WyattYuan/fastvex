"""fastvex services package.

Public API is re-exported here so callers can continue to use::

    from fastvex.services import plan_deploy, deploy_slots, ...

Internal implementation lives in the private sub-modules:
  _helpers.py  – shared utilities (state resilience, backup, validation)
  _project.py  – init / show / validate / history / toolchain
  _deploy.py   – plan_deploy / deploy_slots
  _migrate.py  – migrate_project
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models import Config
from ..project import ProjectPaths
from ..resolve import ResolvedSlot
from ..state_model import ExecutionRecord, Settings, State


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
# Re-exports from sub-modules
# ---------------------------------------------------------------------------

from ._helpers import parse_slot_expr, validate_config  # noqa: E402
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
