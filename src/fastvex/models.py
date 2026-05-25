from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

VALID_MODES = {
    "RED_COMP",
    "BLUE_COMP",
    "SKILL_COMP",
    "RED_DEBUG",
    "BLUE_DEBUG",
    "SKILL_DEBUG",
}


@dataclass(frozen=True)
class Profile:
    profile_id: str
    role_id: str
    route_set: str
    route_key: str
    mode: str
    route: int
    route_name: str
    label: str
    enabled: bool


@dataclass(frozen=True)
class Defaults:
    robot_name: str
    port: str
    name_template: str


@dataclass(frozen=True)
class Role:
    role_id: str
    mode: str
    route_set: str
    label: str
    enabled: bool


@dataclass(frozen=True)
class RouteOption:
    key: str
    route: int
    route_name: str
    label: str
    enabled: bool


@dataclass(frozen=True)
class SlotBinding:
    role_id: str
    route_key_override: str | None


@dataclass(frozen=True)
class Config:
    schema_version: int
    defaults: Defaults
    roles: dict[str, Role]
    routes: dict[str, dict[str, RouteOption]]
    active_route: dict[str, str]
    slots: dict[int, SlotBinding]
    groups: dict[str, list[int]]
    history_retention_count: int = 10


def utc_now_iso() -> str:
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).replace(microsecond=0).isoformat()


def normalize_slots(values: list[int]) -> list[int]:
    unique = sorted(set(values))
    return [v for v in unique if 1 <= v <= 8]


def mode_to_camel(mode: str) -> str:
    return "".join(part.capitalize() for part in mode.split("_"))


def to_state_slot_entry(profile: Profile, final_name: str, timestamp: str) -> dict[str, Any]:
    return {
        "profileId": profile.profile_id,
        "roleId": profile.role_id,
        "routeSet": profile.route_set,
        "routeKey": profile.route_key,
        "mode": profile.mode,
        "route": profile.route,
        "routeName": profile.route_name,
        "label": profile.label,
        "finalName": final_name,
        "uploadedAt": timestamp,
    }


def resolve_profile(config: Config, slot: int) -> Profile:
    binding = config.slots[slot]
    role_id = binding.role_id
    role = config.roles[role_id]
    route_set = role.route_set
    route_key = binding.route_key_override or config.active_route[route_set]
    option = config.routes[route_set][route_key]

    profile_id = f"{role_id}:{route_key}"
    route_name = option.route_name
    label = f"{role.label} / {option.label}" if option.label else role.label

    return Profile(
        profile_id=profile_id,
        role_id=role_id,
        route_set=route_set,
        route_key=route_key,
        mode=role.mode,
        route=option.route,
        route_name=route_name,
        label=label,
        enabled=role.enabled and option.enabled,
    )
