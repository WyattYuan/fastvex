"""Internal helpers shared across service sub-modules.

These utilities are NOT part of the public API (fastvex.services).
Sub-modules import directly from this module; __init__.py only re-exports
the public helpers (parse_slot_expr, validate_config).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ..errors import ValidationError
from ..models import Config, utc_now_iso
from ..resolve import PROGRAM_NAME_LIMIT, merge_build_args, resolve_slot
from ..state_model import State
from ..storage import default_settings, default_state, load_state, save_state


# ---------------------------------------------------------------------------
# Timestamp and backup utilities
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


# ---------------------------------------------------------------------------
# State resilience
# ---------------------------------------------------------------------------


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
    limit = default_settings().history_retention_count
    state.history = history[-limit:] if limit > 0 else []
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
# Public validation helpers (re-exported through services/__init__)
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
