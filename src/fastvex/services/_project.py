"""Project lifecycle commands: init, show, validate, history, clean, toolchain."""
from __future__ import annotations

from . import (
    CleanReport,
    InitReport,
    ShowReport,
    ValidationReport,
    HistoryReport,
    HistoryCleanReport,
    ToolchainReport,
)
from ._helpers import _backup, _load_state_resilient, validate_config
from ..project import DEFAULT_CONFIG, DEFAULT_STATE, LEGACY_CONFIG, resolve_project_paths
from ..storage import (
    default_settings,
    default_state,
    load_config,
    load_settings,
    save_settings,
    save_state,
)


def init_project(
    config: str | None = None,
    state: str | None = None,
    *,
    force: bool = False,
) -> InitReport:
    from ..templates import DEFAULT_CONFIG_TEXT, DEFAULT_LOCAL_GITIGNORE_TEXT

    paths = resolve_project_paths(config=config or DEFAULT_CONFIG, state=state or DEFAULT_STATE, require_config=False)
    legacy_config = paths.root / LEGACY_CONFIG

    config_exists = paths.config.exists()
    state_exists = paths.state.exists()
    settings_exists = paths.settings.exists()
    gitignore_exists = paths.local_gitignore.exists()
    legacy_config_exists = paths.config.name == DEFAULT_CONFIG and legacy_config.exists()

    if force:
        for path in [paths.config, paths.state, paths.settings, paths.local_gitignore]:
            _backup(path)

    config_created = False
    if force or (not config_exists and not legacy_config_exists):
        paths.config.parent.mkdir(parents=True, exist_ok=True)
        paths.config.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
        config_created = True

    paths.local_gitignore.parent.mkdir(parents=True, exist_ok=True)

    state_created = False
    if force or not state_exists:
        save_state(paths.state, default_state())
        state_created = True

    settings_created = False
    if force or not settings_exists:
        save_settings(paths.settings, default_settings())
        settings_created = True

    gitignore_created = False
    if force or not gitignore_exists:
        paths.local_gitignore.write_text(DEFAULT_LOCAL_GITIGNORE_TEXT, encoding="utf-8")
        gitignore_created = True

    return InitReport(
        paths=paths,
        config_created=config_created,
        state_created=state_created,
        settings_created=settings_created,
        gitignore_created=gitignore_created,
        config_exists=config_exists,
        state_exists=state_exists,
        settings_exists=settings_exists,
        gitignore_exists=gitignore_exists,
        legacy_config_exists=legacy_config_exists,
    )


def show_project(config: str | None = None, state: str | None = None) -> ShowReport:
    paths = resolve_project_paths(config=config, state=state)
    return ShowReport(paths=paths, config=load_config(paths.config), state=_load_state_resilient(paths.state))


def validate_project(config: str | None = None, state: str | None = None) -> ValidationReport:
    paths = resolve_project_paths(config=config, state=state)
    loaded_config = load_config(paths.config)
    _, settings_warnings = load_settings(paths.settings)
    _load_state_resilient(paths.state)
    warnings = [*settings_warnings, *validate_config(loaded_config)]
    return ValidationReport(paths=paths, warnings=warnings)


def get_history(config: str | None = None, state: str | None = None) -> HistoryReport:
    paths = resolve_project_paths(config=config, state=state)
    load_config(paths.config)
    return HistoryReport(paths=paths, state=_load_state_resilient(paths.state))


def clean_history(
    config: str | None = None,
    state: str | None = None,
    *,
    keep: int = 10,
) -> HistoryCleanReport:
    paths = resolve_project_paths(config=config, state=state)
    load_config(paths.config)
    loaded_state = _load_state_resilient(paths.state)
    history = list(loaded_state.history)
    if len(history) <= keep:
        return HistoryCleanReport(paths=paths, removed_count=0, kept_count=len(history), state=loaded_state)

    removed = len(history) - keep
    loaded_state.history = history[-keep:] if keep > 0 else []
    save_state(paths.state, loaded_state)
    return HistoryCleanReport(paths=paths, removed_count=removed, kept_count=keep, state=loaded_state)


def clean_project(
    config: str | None = None,
    state: str | None = None,
    *,
    all: bool = False,
) -> CleanReport:
    import shutil

    paths = resolve_project_paths(config=config, state=state, require_config=not all)

    if all:
        fastvex_dir = paths.state.parent
        directory_removed = False
        if fastvex_dir.is_dir():
            shutil.rmtree(fastvex_dir)
            directory_removed = True
        return CleanReport(paths=paths, state_reset=False, directory_removed=directory_removed)

    state_reset = False
    if paths.state.exists():
        save_state(paths.state, default_state())
        state_reset = True

    return CleanReport(paths=paths, state_reset=state_reset, directory_removed=False)


def show_toolchain(rescan: bool = False) -> ToolchainReport:
    from ..toolchain import invalidate_toolchain_cache, resolve_toolchain

    old = resolve_toolchain()

    if rescan:
        invalidate_toolchain_cache()
        old = None

    new = resolve_toolchain()
    rediscovered = old != new
    return ToolchainReport(pros_path=new or "", rediscovered=rediscovered)
