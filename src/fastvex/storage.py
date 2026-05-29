from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from .errors import ValidationError
from .models import Config
from .state_model import Settings, State


def _ensure_fastvex_gitignore(dirpath: Path) -> None:
    """Write .gitignore with '*' into the .fastvex directory if missing."""
    from .templates import DEFAULT_LOCAL_GITIGNORE_TEXT

    gitignore = dirpath / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(DEFAULT_LOCAL_GITIGNORE_TEXT, encoding="utf-8")


def _format_validation_error(error: PydanticValidationError) -> str:
    first = error.errors()[0] if error.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []))
    message = str(first.get("msg", error))
    if location:
        return f"{location}: {message}"
    return message


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValidationError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValidationError("Config root must be a mapping")
    return data


def load_config(path: Path) -> Config:
    data = load_yaml(path)
    if data.get("schemaVersion") != 2:
        raise ValidationError("fastvex.yaml uses schemaVersion 1. Run: fastvex migrate")
    try:
        return Config.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(_format_validation_error(exc)) from exc


def default_state() -> State:
    return State()


def default_settings() -> Settings:
    return Settings()


def load_state(path: Path) -> State:
    if not path.exists():
        return default_state()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"state file is corrupt: {path}") from exc
    if not isinstance(data, dict):
        raise ValidationError("state file must contain a JSON object")
    try:
        return State.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(_format_validation_error(exc)) from exc


def save_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_fastvex_gitignore(path.parent)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(state.model_dump(by_alias=True, mode="json"), f, ensure_ascii=True, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def load_settings(path: Path) -> tuple[Settings, list[str]]:
    if not path.exists():
        return default_settings(), []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"settings file is corrupt: {path}") from exc
    if not isinstance(data, dict):
        raise ValidationError("settings file must contain a JSON object")
    warnings = [f"unknown settings field: {key}" for key in data if key not in {"historyRetentionCount"}]
    try:
        return Settings.model_validate(data), warnings
    except PydanticValidationError as exc:
        raise ValidationError(_format_validation_error(exc)) from exc


def save_settings(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_fastvex_gitignore(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(settings.model_dump(by_alias=True, mode="json"), f, ensure_ascii=True, indent=2)
        f.write("\n")
