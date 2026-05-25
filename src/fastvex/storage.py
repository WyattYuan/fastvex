from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from socket import gethostname
from typing import Any

import yaml

from .models import Config, Defaults, Role, RouteOption, SlotBinding, VALID_MODES, normalize_slots


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


def _parse_slot_binding(slot: int, raw_value: Any) -> tuple[str, str | None]:
    if isinstance(raw_value, dict):
        role_id = str(raw_value.get("role", "")).strip()
        route_raw = raw_value.get("route")
        route_key = str(route_raw).strip() if route_raw is not None else None
        if not role_id:
            raise ValidationError(f"slot '{slot}' mapping form requires 'role'")
        return role_id, route_key or None

    raise ValidationError(
        f"slot '{slot}' must use mapping form: {{role: <role-id>, route: <optional-route-key>}}"
    )


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

    schema_version = int(data.get("schemaVersion", 1))

    defaults_raw = data.get("defaults", {})
    defaults = Defaults(
        robot_name=str(defaults_raw.get("robotName", "Sparkle")),
        port=str(defaults_raw.get("port", "")),
        name_template=str(defaults_raw.get("nameTemplate", "{modeCamel}{routeSuffix}-{robotName}")),
    )

    roles_raw = data.get("roles", {})
    if not isinstance(roles_raw, dict) or not roles_raw:
        raise ValidationError("roles must be a non-empty mapping")

    roles: dict[str, Role] = {}
    for role_id, raw in roles_raw.items():
        if not isinstance(raw, dict):
            raise ValidationError(f"role '{role_id}' must be a mapping")
        mode = str(raw.get("mode", "")).upper()
        route_set = str(raw.get("routeSet", "")).strip().lower()
        label = str(raw.get("label", role_id))
        enabled = bool(raw.get("enabled", True))

        if mode not in VALID_MODES:
            raise ValidationError(f"role '{role_id}' has invalid mode '{mode}'")
        if not route_set:
            raise ValidationError(f"role '{role_id}' must define routeSet")

        roles[role_id] = Role(
            role_id=role_id,
            mode=mode,
            route_set=route_set,
            label=label,
            enabled=enabled,
        )

    routes_raw = data.get("routes", {})
    if not isinstance(routes_raw, dict) or not routes_raw:
        raise ValidationError("routes must be a non-empty mapping")

    routes: dict[str, dict[str, RouteOption]] = {}
    for route_set, options_raw in routes_raw.items():
        route_set_key = str(route_set).strip().lower()
        if not isinstance(options_raw, dict) or not options_raw:
            raise ValidationError(f"routes.{route_set_key} must be a non-empty mapping")

        set_options: dict[str, RouteOption] = {}
        for option_key, raw in options_raw.items():
            key = str(option_key).strip()
            if not isinstance(raw, dict):
                raise ValidationError(f"routes.{route_set_key}.{key} must be a mapping")

            route = int(raw.get("route", -1))
            route_name = str(raw.get("routeName", key))
            label = str(raw.get("label", key))
            enabled = bool(raw.get("enabled", True))
            if route < 0:
                raise ValidationError(
                    f"routes.{route_set_key}.{key} has invalid route '{route}'"
                )

            set_options[key] = RouteOption(
                key=key,
                route=route,
                route_name=route_name,
                label=label,
                enabled=enabled,
            )

        routes[route_set_key] = set_options

    active_raw = data.get("activeRoute", {})
    if not isinstance(active_raw, dict):
        raise ValidationError("activeRoute must be a mapping")

    active_route: dict[str, str] = {}
    for route_set, key in active_raw.items():
        rs = str(route_set).strip().lower()
        rk = str(key).strip()
        if rs not in routes:
            raise ValidationError(f"activeRoute references unknown route set '{rs}'")
        if rk not in routes[rs]:
            raise ValidationError(
                f"activeRoute.{rs} references unknown route key '{rk}'"
            )
        active_route[rs] = rk

    # Each route set referenced by a role must have an active route.
    for role_id, role in roles.items():
        if role.route_set not in routes:
            raise ValidationError(
                f"role '{role_id}' references unknown route set '{role.route_set}'"
            )
        if role.route_set not in active_route:
            raise ValidationError(
                f"activeRoute missing route set '{role.route_set}' for role '{role_id}'"
            )

    slots_raw = data.get("slots", {})
    if not isinstance(slots_raw, dict):
        raise ValidationError("slots must be a mapping")

    slots: dict[int, SlotBinding] = {}
    for k, v in slots_raw.items():
        slot = int(k)
        if slot < 1 or slot > 8:
            raise ValidationError(f"slot '{slot}' out of range 1-8")

        role_id, route_override = _parse_slot_binding(slot, v)
        if role_id not in roles:
            raise ValidationError(f"slot '{slot}' references unknown role '{role_id}'")

        role = roles[role_id]
        if route_override is not None and route_override not in routes[role.route_set]:
            raise ValidationError(
                f"slot '{slot}' override route '{route_override}' is not valid "
                f"for route set '{role.route_set}'"
            )

        slots[slot] = SlotBinding(role_id=role_id, route_key_override=route_override)

    missing_slots = [s for s in range(1, 9) if s not in slots]
    if missing_slots:
        raise ValidationError(f"slots must define 1-8, missing: {missing_slots}")

    groups_raw = data.get("groups", {})
    if not isinstance(groups_raw, dict):
        raise ValidationError("groups must be a mapping")

    groups: dict[str, list[int]] = {}
    for name, values in groups_raw.items():
        if not isinstance(values, list):
            raise ValidationError(f"group '{name}' must be a list")
        casted = [int(x) for x in values]
        for slot in casted:
            if slot < 1 or slot > 8:
                raise ValidationError(f"group '{name}' includes out-of-range slot '{slot}'")
        slots_in_group = normalize_slots(casted)
        if not slots_in_group:
            raise ValidationError(f"group '{name}' cannot be empty")
        groups[name] = slots_in_group

    return Config(
        schema_version=schema_version,
        defaults=defaults,
        roles=roles,
        routes=routes,
        active_route=active_route,
        slots=slots,
        groups=groups,
        history_retention_count=int(data.get("historyRetentionCount", 10)),
    )


def default_state() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "createdAt": None,
        "updatedAt": None,
        "lastRobotName": "Sparkle",
        "lastPort": "",
        "currentSlots": {},
        "history": [],
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_state()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValidationError("state file must contain a JSON object")
    defaults = default_state()
    defaults.update(data)
    return defaults


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=True, indent=2)
        f.write("\n")
