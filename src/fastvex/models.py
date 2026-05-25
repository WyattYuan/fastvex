from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_MODES = {
    "RED_COMP",
    "BLUE_COMP",
    "SKILL_COMP",
    "RED_DEBUG",
    "BLUE_DEBUG",
    "SKILL_DEBUG",
}


class FastVexModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class Profile(FastVexModel):
    profile_id: str
    role_id: str
    route_set: str
    route_key: str
    mode: str
    route: int
    route_name: str
    label: str
    enabled: bool


class Defaults(FastVexModel):
    robot_name: str = Field("Sparkle", alias="robotName")
    port: str = ""
    name_template: str = Field("{modeCamel}{routeSuffix}-{robotName}", alias="nameTemplate")


class Role(FastVexModel):
    mode: str
    route_set: str = Field(alias="routeSet")
    label: str = ""
    enabled: bool = True
    role_id: str = ""

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, value: Any) -> str:
        mode = str(value).upper()
        if mode not in VALID_MODES:
            raise ValueError(f"invalid mode '{mode}'")
        return mode

    @field_validator("route_set", mode="before")
    @classmethod
    def normalize_route_set(cls, value: Any) -> str:
        route_set = str(value).strip().lower()
        if not route_set:
            raise ValueError("must define routeSet")
        return route_set


class RouteOption(FastVexModel):
    route: int
    route_name: str = Field(alias="routeName")
    label: str = ""
    enabled: bool = True
    key: str = ""

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"invalid route '{value}'")
        return value


class SlotBinding(FastVexModel):
    role_id: str = Field(alias="role")
    route_key_override: str | None = Field(None, alias="route")

    @field_validator("role_id", mode="before")
    @classmethod
    def normalize_role_id(cls, value: Any) -> str:
        role_id = str(value).strip()
        if not role_id:
            raise ValueError("mapping form requires 'role'")
        return role_id

    @field_validator("route_key_override", mode="before")
    @classmethod
    def normalize_route_key(cls, value: Any) -> str | None:
        if value is None:
            return None
        route_key = str(value).strip()
        return route_key or None


class Config(FastVexModel):
    schema_version: int = Field(1, alias="schemaVersion")
    defaults: Defaults = Field(default_factory=Defaults)
    roles: dict[str, Role]
    routes: dict[str, dict[str, RouteOption]]
    active_route: dict[str, str] = Field(alias="activeRoute")
    slots: dict[int, SlotBinding]
    groups: dict[str, list[int]] = Field(default_factory=dict)
    history_retention_count: int = Field(10, alias="historyRetentionCount")

    @field_validator("roles", mode="before")
    @classmethod
    def validate_roles_raw(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not value:
            raise ValueError("roles must be a non-empty mapping")
        return value

    @field_validator("routes", mode="before")
    @classmethod
    def validate_routes_raw(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not value:
            raise ValueError("routes must be a non-empty mapping")
        return value

    @field_validator("active_route", mode="before")
    @classmethod
    def validate_active_route_raw(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            raise ValueError("activeRoute must be a mapping")
        return {str(k).strip().lower(): str(v).strip() for k, v in value.items()}

    @field_validator("slots", mode="before")
    @classmethod
    def validate_slots_raw(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            raise ValueError("slots must be a mapping")
        normalized: dict[int, Any] = {}
        for raw_slot, raw_binding in value.items():
            slot = int(raw_slot)
            if slot < 1 or slot > 8:
                raise ValueError(f"slot '{slot}' out of range 1-8")
            normalized[slot] = raw_binding
        return normalized

    @field_validator("groups", mode="before")
    @classmethod
    def validate_groups_raw(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("groups must be a mapping")
        normalized: dict[str, list[int]] = {}
        for name, raw_slots in value.items():
            if not isinstance(raw_slots, list):
                raise ValueError(f"group '{name}' must be a list")
            casted = [int(slot) for slot in raw_slots]
            for slot in casted:
                if slot < 1 or slot > 8:
                    raise ValueError(f"group '{name}' includes out-of-range slot '{slot}'")
            slots = normalize_slots(casted)
            if not slots:
                raise ValueError(f"group '{name}' cannot be empty")
            normalized[str(name)] = slots
        return normalized

    @model_validator(mode="after")
    def enrich_and_validate(self) -> Config:
        self.roles = {
            role_id: role.model_copy(
                update={
                    "role_id": role_id,
                    "label": role.label or role_id,
                }
            )
            for role_id, role in self.roles.items()
        }

        normalized_routes: dict[str, dict[str, RouteOption]] = {}
        for route_set, options in self.routes.items():
            route_set_key = str(route_set).strip().lower()
            if not options:
                raise ValueError(f"routes.{route_set_key} must be a non-empty mapping")
            normalized_routes[route_set_key] = {
                key: option.model_copy(
                    update={
                        "key": key,
                        "route_name": option.route_name or key,
                        "label": option.label or key,
                    }
                )
                for key, option in options.items()
            }
        self.routes = normalized_routes

        for route_set, key in self.active_route.items():
            if route_set not in self.routes:
                raise ValueError(f"activeRoute references unknown route set '{route_set}'")
            if key not in self.routes[route_set]:
                raise ValueError(f"activeRoute.{route_set} references unknown route key '{key}'")

        for role_id, role in self.roles.items():
            if role.route_set not in self.routes:
                raise ValueError(
                    f"role '{role_id}' references unknown route set '{role.route_set}'"
                )
            if role.route_set not in self.active_route:
                raise ValueError(
                    f"activeRoute missing route set '{role.route_set}' for role '{role_id}'"
                )

        for slot, binding in self.slots.items():
            if binding.role_id not in self.roles:
                raise ValueError(f"slot '{slot}' references unknown role '{binding.role_id}'")
            role = self.roles[binding.role_id]
            if (
                binding.route_key_override is not None
                and binding.route_key_override not in self.routes[role.route_set]
            ):
                raise ValueError(
                    f"slot '{slot}' override route '{binding.route_key_override}' is not valid "
                    f"for route set '{role.route_set}'"
                )

        missing_slots = [slot for slot in range(1, 9) if slot not in self.slots]
        if missing_slots:
            raise ValueError(f"slots must define 1-8, missing: {missing_slots}")

        return self


def utc_now_iso() -> str:
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).replace(microsecond=0).isoformat()


def normalize_slots(values: list[int]) -> list[int]:
    unique = sorted(set(values))
    return [value for value in unique if 1 <= value <= 8]


def mode_to_camel(mode: str) -> str:
    return "".join(part.capitalize() for part in mode.split("_"))


def resolve_profile(config: Config, slot: int) -> Profile:
    binding = config.slots[slot]
    role_id = binding.role_id
    role = config.roles[role_id]
    route_set = role.route_set
    route_key = binding.route_key_override or config.active_route[route_set]
    option = config.routes[route_set][route_key]

    profile_id = f"{role_id}:{route_key}"
    label = f"{role.label} / {option.label}" if option.label else role.label

    return Profile(
        profile_id=profile_id,
        role_id=role_id,
        route_set=route_set,
        route_key=route_key,
        mode=role.mode,
        route=option.route,
        route_name=option.route_name,
        label=label,
        enabled=role.enabled and option.enabled,
    )
