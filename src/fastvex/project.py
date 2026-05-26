from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .storage import ValidationError

DEFAULT_CONFIG = "fastvex.yaml"
LEGACY_CONFIG = "vex_upload_config.yaml"
DEFAULT_STATE = ".fastvex/state.json"
DEFAULT_SETTINGS = ".fastvex/settings.json"
DEFAULT_LOCAL_GITIGNORE = ".fastvex/.gitignore"


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    config: Path
    state: Path
    settings: Path
    local_gitignore: Path
    legacy_config: bool = False


def resolve_relative_to(base: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return base / path


def find_config(start: Path) -> tuple[Path, bool] | None:
    current = start.resolve()
    search_dirs = [current, *current.parents]
    for directory in search_dirs:
        candidate = directory / DEFAULT_CONFIG
        if candidate.exists():
            return candidate, False
        legacy = directory / LEGACY_CONFIG
        if legacy.exists():
            return legacy, True
    return None


def resolve_project_paths(
    *,
    config: str | None = None,
    state: str | None = None,
    require_config: bool = True,
) -> ProjectPaths:
    if config:
        config_path = Path(config)
        if not config_path.is_absolute():
            config_path = Path.cwd() / config_path
        config_path = config_path.resolve()
        legacy_config = config_path.name == LEGACY_CONFIG
        if require_config and not config_path.exists():
            raise ValidationError(f"Config file not found: {config_path}")
    else:
        found = find_config(Path.cwd())
        if found is None:
            if require_config:
                raise ValidationError(
                    f"Config file not found. Run 'fastvex init' or pass --config {DEFAULT_CONFIG}."
                )
            config_path = (Path.cwd() / DEFAULT_CONFIG).resolve()
            legacy_config = False
        else:
            config_path, legacy_config = found

    root = config_path.parent
    state_path = (
        resolve_relative_to(root, state).resolve()
        if state
        else (root / DEFAULT_STATE).resolve()
    )
    settings_path = (root / DEFAULT_SETTINGS).resolve()
    local_gitignore_path = (root / DEFAULT_LOCAL_GITIGNORE).resolve()

    return ProjectPaths(
        root=root,
        config=config_path,
        state=state_path,
        settings=settings_path,
        local_gitignore=local_gitignore_path,
        legacy_config=legacy_config,
    )
