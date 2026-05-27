"""v1 -> v2 config migration logic."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import MigrateReport
from ._helpers import _backup_v1
from ..models import Config
from ..project import DEFAULT_CONFIG, LEGACY_CONFIG
from ..errors import ValidationError
from ..storage import load_yaml


def _to_lower_camel(value: object) -> str:
    raw = str(value).strip()
    if not raw:
        return "unnamed"
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", raw) if part]
    if not parts:
        return "unnamed"
    if len(parts) == 1:
        text = parts[0]
        return text[0].lower() + text[1:]
    first = parts[0].lower()
    rest = [part[:1].upper() + part[1:] for part in parts[1:]]
    result = first + "".join(rest)
    if not result[0].isalpha() or not result[0].islower():
        result = f"v{result[:1].upper()}{result[1:]}"
    return result


def _find_migration_source(config: str | None = None) -> Path:
    if config:
        path = Path(config)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise ValidationError(f"Config file not found: {path.resolve()}")
        return path.resolve()

    current = Path.cwd().resolve()
    for directory in [current, *current.parents]:
        fastvex = directory / DEFAULT_CONFIG
        legacy = directory / LEGACY_CONFIG
        if fastvex.exists():
            return fastvex.resolve()
        if legacy.exists():
            return legacy.resolve()
    raise ValidationError(f"Config file not found. Expected {DEFAULT_CONFIG} or {LEGACY_CONFIG}.")


def _migrate_v1_data(data: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = [
        "generated schema v2 draft; review every slot profile+route before deploying"
    ]

    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    robot_name = str(defaults.get("robotName") or "Sparkle")  # type: ignore[union-attr]

    raw_roles = data.get("roles")
    raw_routes = data.get("routes")
    raw_slots = data.get("slots")
    raw_active = data.get("activeRoute") if isinstance(data.get("activeRoute"), dict) else {}
    raw_groups = data.get("groups") if isinstance(data.get("groups"), dict) else {}

    if not isinstance(raw_roles, dict) or not raw_roles:
        raise ValidationError("v1 roles must be a non-empty mapping")
    if not isinstance(raw_routes, dict) or not raw_routes:
        raise ValidationError("v1 routes must be a non-empty mapping")
    if not isinstance(raw_slots, dict):
        raise ValidationError("v1 slots must be a mapping")

    route_set_map = {str(key): _to_lower_camel(key) for key in raw_routes}
    role_map = {str(key): _to_lower_camel(key) for key in raw_roles}
    route_key_map: dict[tuple[str, str], str] = {}

    alliances: dict[str, object] = {}
    for old_set, raw_options in raw_routes.items():
        if not isinstance(raw_options, dict) or not raw_options:
            raise ValidationError(f"v1 routes.{old_set} must be a non-empty mapping")
        alliance_key = route_set_map[str(old_set)]
        routes: dict[str, object] = {}
        for old_key, raw_option in raw_options.items():
            route_key = _to_lower_camel(old_key)
            route_key_map[(str(old_set), str(old_key))] = route_key
            route_number = 0
            if isinstance(raw_option, dict):
                route_number = int(raw_option.get("route", 0))
            routes[route_key] = {"buildArgs": {"ROUTE": route_number}}
        alliances[alliance_key] = {"routes": routes}

    profiles: dict[str, object] = {}
    role_route_set: dict[str, str] = {}
    for old_role, raw_role in raw_roles.items():
        if not isinstance(raw_role, dict):
            raise ValidationError(f"v1 role '{old_role}' must be a mapping")
        profile_key = role_map[str(old_role)]
        old_route_set = str(raw_role.get("routeSet", "")).strip()
        alliance_key = route_set_map.get(old_route_set, _to_lower_camel(old_route_set))
        role_route_set[str(old_role)] = old_route_set
        profiles[profile_key] = {
            "alliance": alliance_key,
            "buildArgs": {"MODE": str(raw_role.get("mode", "")).strip()},
        }
        if not str(raw_role.get("mode", "")).strip():
            warnings.append(f"profile '{profile_key}' migrated with empty MODE")

    slots: dict[int, object] = {}
    for slot in range(1, 9):
        raw_binding = raw_slots.get(slot, raw_slots.get(str(slot)))
        if raw_binding is None:
            slots[slot] = "empty"
            warnings.append(f"slot {slot} was missing in v1 config and was migrated as empty")
            continue
        if not isinstance(raw_binding, dict):
            raise ValidationError(f"v1 slot {slot} must be a mapping")
        old_role = str(raw_binding.get("role", "")).strip()
        if old_role not in role_map:
            raise ValidationError(f"v1 slot {slot} references unknown role '{old_role}'")
        old_route_set = role_route_set[old_role]
        raw_route = raw_binding.get("route") or raw_active.get(old_route_set)  # type: ignore[union-attr]
        if raw_route is None:
            raise ValidationError(f"v1 slot {slot} has no route and activeRoute.{old_route_set} is missing")
        route_key = route_key_map.get((old_route_set, str(raw_route)), _to_lower_camel(raw_route))
        slots[slot] = {
            "profile": role_map[old_role],
            "route": route_key,
        }

    slot_groups: dict[str, list[int]] = {"all": list(range(1, 9))}
    for old_group, raw_group_slots in raw_groups.items():  # type: ignore[union-attr]
        if not isinstance(raw_group_slots, list):
            warnings.append(f"skipped v1 group '{old_group}' because it is not a list")
            continue
        group_key = _to_lower_camel(old_group)
        if group_key == "all":
            group_key = "allMigrated"
        slot_groups[group_key] = [int(slot) for slot in raw_group_slots]

    migrated = {
        "schemaVersion": 2,
        "robot": {"name": robot_name},
        "programName": {"template": "{profile}-{route}-{robot}"},
        "alliances": alliances,
        "profiles": profiles,
        "slots": slots,
        "slotGroups": slot_groups,
    }
    Config.model_validate(migrated)
    return migrated, warnings


def migrate_project(
    config: str | None = None,
    output: str | None = None,
    *,
    write: bool = False,
) -> MigrateReport:
    source = _find_migration_source(config)
    data = load_yaml(source)
    if data.get("schemaVersion") == 2:
        raise ValidationError("config already uses schemaVersion 2")
    migrated, warnings = _migrate_v1_data(data)

    if write:
        output_path = source.with_name(DEFAULT_CONFIG)
        if output_path.exists():
            _backup_v1(output_path)
    else:
        output_path = Path(output) if output else source.with_name("fastvex.v2.yaml")
        if not output_path.is_absolute():
            output_path = source.parent / output_path
        if output_path.exists():
            raise ValidationError(f"output file already exists: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(migrated, sort_keys=False, allow_unicode=True)
    output_path.write_text(text, encoding="utf-8")
    return MigrateReport(
        source=source,
        output=output_path.resolve(),
        wrote_in_place=write,
        warnings=warnings,
    )
