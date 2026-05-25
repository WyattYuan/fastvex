from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from socket import gethostname
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from .models import Config
from .state_model import State


class ValidationError(Exception):
    pass


def get_git_username() -> str:
    try:
        return subprocess.check_output(
            ["git", "config", "user.name"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.environ.get("USERNAME", os.environ.get("USER", "unknown"))


def get_hostname() -> str:
    return gethostname()


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
    try:
        return Config.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(_format_validation_error(exc)) from exc


def default_state() -> State:
    return State()


def load_state(path: Path) -> State:
    if not path.exists():
        return default_state()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValidationError("state file must contain a JSON object")
    try:
        return State.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(_format_validation_error(exc)) from exc


def save_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state.model_dump(by_alias=True, mode="json"), f, ensure_ascii=True, indent=2)
        f.write("\n")
