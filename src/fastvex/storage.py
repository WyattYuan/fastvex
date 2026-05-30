from __future__ import annotations

import json
import os
from difflib import get_close_matches
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from .errors import ValidationError
from .state_model import Settings, State


def _ensure_fastvex_gitignore(dirpath: Path) -> None:
    """Write .gitignore with '*' into the .fastvex directory if missing."""
    from .templates import DEFAULT_LOCAL_GITIGNORE_TEXT

    gitignore = dirpath / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(DEFAULT_LOCAL_GITIGNORE_TEXT, encoding="utf-8")


# ── Known field names per nesting level (for pre-validation) ──────────────
# Lazily built to avoid import-time overhead.

_KNOWN_FIELDS: dict[str, set[str]] | None = None


def _get_known_fields() -> dict[str, set[str]]:
    global _KNOWN_FIELDS
    if _KNOWN_FIELDS is not None:
        return _KNOWN_FIELDS
    from .models import Alliance, Config, ProgramName, Robot, SlotBinding

    def _names(model: type) -> set[str]:
        result: set[str] = set()
        for name, field in model.model_fields.items():
            result.add(name)
            if field.alias:
                result.add(field.alias)
        return result

    _KNOWN_FIELDS = {
        "__root__": _names(Config),
        "robot": _names(Robot),
        "programName": _names(ProgramName),
        "alliance": _names(Alliance),
        "slotBinding": _names(SlotBinding),
    }
    return _KNOWN_FIELDS


def _snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _validate_config_keys(data: dict[str, Any], level: str = "__root__", prefix: str = "") -> list[str]:
    """Pre-validate YAML field names; return list of user-facing error messages."""
    known = _get_known_fields()
    expected = known.get(level, set())
    errors: list[str] = []

    for key in data:
        if not isinstance(key, str):
            continue
        if key in expected:
            # Recurse into known sub-objects
            child = data[key]
            if not isinstance(child, dict):
                continue
            next_level: str | None = None
            if level == "__root__":
                if key == "robot":
                    next_level = "robot"
                elif key in ("programName", "program_name"):
                    next_level = "programName"
            elif level == "alliance" and key == "routes":
                # route values are user-defined, validated by model
                for route_val in child.values():
                    if isinstance(route_val, dict):
                        errors.extend(
                            _validate_config_keys(route_val, "slotBinding", f"{prefix}{key}.")
                        )
                continue
            if next_level:
                errors.extend(
                    _validate_config_keys(child, next_level, f"{prefix}{key}.")
                )
        else:
            loc = f"{prefix}{key}" if prefix else key
            camel = _snake_to_camel(key)
            if camel in expected:
                errors.append(
                    f"'{loc}': unknown field (did you mean '{camel}'?)"
                )
            else:
                suggestion = get_close_matches(key, expected, n=1, cutoff=0.6)
                if suggestion:
                    errors.append(
                        f"'{loc}': unknown field (did you mean '{suggestion[0]}'?)"
                    )
                else:
                    errors.append(
                        f"'{loc}': unknown field; expected one of: {', '.join(sorted(expected))}"
                    )
    return errors


def _format_validation_error(error: PydanticValidationError) -> str:
    lines: list[str] = []
    for err in error.errors()[:3]:
        loc = ".".join(str(p) for p in err.get("loc", []))
        msg = err.get("msg", "")
        ctx = err.get("ctx", {})
        input_val = err.get("input")

        # Prefer explicit error message from ctx (custom validators put it there)
        detail = ctx.get("error") if isinstance(ctx, dict) else None
        if detail:
            detail_str = str(detail)
        elif msg == "Extra inputs are not permitted" and isinstance(input_val, dict):
            unknown = sorted(str(k) for k in input_val if isinstance(k, str))
            detail_str = f"unexpected field(s): {', '.join(unknown)}"
        elif "String" in msg or "string" in msg.lower():
            detail_str = "must be a string"
        elif msg == "Input should be a valid integer":
            detail_str = "must be an integer"
        elif msg == "Field required":
            detail_str = "this field is required"
        else:
            detail_str = msg

        if loc:
            lines.append(f"{loc}: {detail_str}")
        else:
            lines.append(detail_str)
    return "; ".join(lines) if lines else str(error)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValidationError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValidationError("Config root must be a mapping")
    return data


def load_config(path: Path):
    from .models import Config

    data = load_yaml(path)
    if data.get("schemaVersion") != 2:
        raise ValidationError("fastvex.yaml uses schemaVersion 1. Run: fastvex migrate")
    # Pre-validate field names for clearer error messages
    field_errors = _validate_config_keys(data)
    if field_errors:
        raise ValidationError(field_errors[0] if len(field_errors) == 1 else "\n".join(field_errors))
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
