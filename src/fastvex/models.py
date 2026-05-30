"""fastvex configuration schema (Pydantic models and validators).

Business logic that operates *on* the resolved config lives in resolve.py.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

KEY_RE = re.compile(r"^[a-z]([A-Za-z0-9]*(_[a-z0-9][A-Za-z0-9]*)*)?$")
BUILD_ARG_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PROGRAM_NAME_VARS = {"robot", "team", "profile", "alliance", "route", "slot"}


class FastVexModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class BuildArg(FastVexModel):
    name: str
    value: str


class Robot(FastVexModel):
    name: str
    team: str | None = None

    @field_validator("name", "team")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("must not be empty")
        return text


class ProgramName(FastVexModel):
    template: str = "{profile}-{route}-{robot}"

    @field_validator("template")
    @classmethod
    def validate_template(cls, value: str) -> str:
        from string import Formatter

        text = str(value).strip()
        if not text:
            raise ValueError("programName.template must not be empty")
        for _, field_name, format_spec, conversion in Formatter().parse(text):
            if field_name is None:
                continue
            if format_spec or conversion:
                raise ValueError(
                    f"programName.template does not support format specs or conversions "
                    f"(found '{{{field_name}}}' with extra syntax); "
                    f"use simple placeholders like '{{robot}}' or '{{profile}}'"
                )
            if field_name not in PROGRAM_NAME_VARS:
                allowed = ", ".join(sorted(PROGRAM_NAME_VARS))
                raise ValueError(
                    f"unknown placeholder '{{{field_name}}}' in programName.template; "
                    f"allowed: {allowed}"
                )
        return text


class Route(FastVexModel):
    build_args: dict[str, str] = Field(default_factory=dict, alias="buildArgs")

    @field_validator("build_args", mode="before")
    @classmethod
    def normalize_build_args(cls, value: Any) -> dict[str, str]:
        return normalize_build_args(value)


class Alliance(FastVexModel):
    routes: dict[str, Route]

    @field_validator("routes", mode="before")
    @classmethod
    def validate_routes(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not value:
            raise ValueError("routes must be a non-empty mapping")
        validate_keys(value, "route")
        return value


class Profile(FastVexModel):
    alliance: str
    build_args: dict[str, str] = Field(default_factory=dict, alias="buildArgs")

    @field_validator("alliance")
    @classmethod
    def validate_alliance(cls, value: str) -> str:
        text = str(value).strip()
        if not KEY_RE.match(text):
            raise ValueError(
                f"alliance reference '{text}' is invalid: "
                f"must start with a lowercase letter, use camelCase or snake_case "
                f"(e.g. 'redAlliance' or 'red_alliance')"
            )
        return text

    @field_validator("build_args", mode="before")
    @classmethod
    def normalize_profile_build_args(cls, value: Any) -> dict[str, str]:
        return normalize_build_args(value)


class SlotBinding(FastVexModel):
    profile: str
    route: str

    @field_validator("profile", "route")
    @classmethod
    def validate_ref(cls, value: str) -> str:
        text = str(value).strip()
        if not KEY_RE.match(text):
            raise ValueError(
                f"'{text}' is invalid: "
                f"must start with a lowercase letter, use camelCase or snake_case "
                f"(e.g. 'myProfile' or 'my_profile')"
            )
        return text


class Config(FastVexModel):
    schema_version: int = Field(2, alias="schemaVersion")
    robot: Robot
    program_name: ProgramName = Field(default_factory=ProgramName, alias="programName")
    alliances: dict[str, Alliance]
    profiles: dict[str, Profile]
    slots: dict[int, SlotBinding | None]
    slot_groups: dict[str, list[int]] = Field(default_factory=dict, alias="slotGroups")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        if value != 2:
            raise ValueError("fastvex.yaml uses schemaVersion 1. Run: fastvex migrate")
        return value

    @field_validator("alliances", "profiles", mode="before")
    @classmethod
    def validate_keyed_mapping(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not value:
            raise ValueError("must be a non-empty mapping")
        validate_keys(value, "key")
        return value

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
            if isinstance(raw_binding, str) and raw_binding == "empty":
                normalized[slot] = None
            elif isinstance(raw_binding, dict):
                normalized[slot] = raw_binding
            else:
                raise ValueError("slot must be 'empty' or a mapping with profile and route")
        return normalized

    @field_validator("slot_groups", mode="before")
    @classmethod
    def validate_slot_groups_raw(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("slotGroups must be a mapping")
        validate_keys(value, "slot group")
        normalized: dict[str, list[int]] = {}
        for name, raw_slots in value.items():
            if not isinstance(raw_slots, list):
                raise ValueError(f"slotGroups.{name} must be a list")
            slots: list[int] = []
            for raw_slot in raw_slots:
                slot = int(raw_slot)
                if slot < 1 or slot > 8:
                    raise ValueError(f"slotGroups.{name} includes out-of-range slot '{slot}'")
                slots.append(slot)
            normalized[str(name)] = slots
        return normalized

    @model_validator(mode="after")
    def validate_refs(self) -> Config:
        missing_slots = [slot for slot in range(1, 9) if slot not in self.slots]
        if missing_slots:
            raise ValueError(f"slots must define 1-8, missing: {missing_slots}")

        for profile_key, profile in self.profiles.items():
            if profile.alliance not in self.alliances:
                raise ValueError(
                    f"profile '{profile_key}' references unknown alliance '{profile.alliance}'"
                )

        for slot, binding in self.slots.items():
            if binding is None:
                continue
            if binding.profile not in self.profiles:
                raise ValueError(f"slot '{slot}' references unknown profile '{binding.profile}'")
            profile = self.profiles[binding.profile]
            routes = self.alliances[profile.alliance].routes
            if binding.route not in routes:
                raise ValueError(
                    f"slot '{slot}' route '{binding.route}' is not valid for "
                    f"alliance '{profile.alliance}'"
                )

        return self


# ── Shared utilities ──────────────────────────────────────────────────────────


def utc_now_iso() -> str:
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).replace(microsecond=0).isoformat()


def validate_keys(mapping: dict[Any, Any], label: str) -> None:
    for key in mapping:
        text = str(key)
        if not KEY_RE.match(text):
            raise ValueError(
                f"{label} key '{text}' is invalid: must start with a lowercase letter, "
                f"use camelCase or snake_case (e.g. 'myKey' or 'my_key')"
            )


def normalize_build_args(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("buildArgs must be a mapping")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not BUILD_ARG_RE.match(key):
            raise ValueError(f"buildArg '{key}' must match [A-Za-z_][A-Za-z0-9_]*")
        if isinstance(raw_value, bool) or isinstance(raw_value, (list, dict)) or raw_value is None:
            raise ValueError(f"buildArg '{key}' must be a string or number")
        if not isinstance(raw_value, (str, int, float)):
            raise ValueError(f"buildArg '{key}' must be a string or number")
        normalized[key] = str(raw_value)
    return normalized
