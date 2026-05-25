from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from .models import Profile


class StateModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore"
    )

class StepRecord(StateModel):
    ok: bool = False
    command: list[str] = Field(default_factory=list)
    duration_sec: float = 0.0
    returncode: int | None = None
    output: str = ""
    error: str = ""


class StateSlotEntry(StateModel):
    profile_id: str
    role_id: str
    route_set: str
    route_key: str
    mode: str
    route: int
    route_name: str
    label: str
    final_name: str
    uploaded_at: str

    @classmethod
    def from_profile(cls, profile: Profile, final_name: str, timestamp: str) -> StateSlotEntry:
        return cls(
            profile_id=profile.profile_id,
            role_id=profile.role_id,
            route_set=profile.route_set,
            route_key=profile.route_key,
            mode=profile.mode,
            route=profile.route,
            route_name=profile.route_name,
            label=profile.label,
            final_name=final_name,
            uploaded_at=timestamp,
        )


class SlotExecutionResult(StateModel):
    slot: int = 0
    profile_id: str = ""
    role_id: str = ""
    route_set: str = ""
    route_key: str = ""
    mode: str = ""
    route: int = 0
    final_name: str = ""
    build: StepRecord = Field(default_factory=StepRecord)
    upload: StepRecord = Field(default_factory=StepRecord)
    dry_run: bool = False


class ExecutionRecord(StateModel):
    started_at: str = ""
    ended_at: str = ""
    status: str = "unknown"
    robot_name: str = ""
    port: str = ""
    requested_slots: list[int] = Field(default_factory=list)
    before_snapshot: dict[int, StateSlotEntry] = Field(default_factory=dict)
    after_snapshot: dict[int, StateSlotEntry] = Field(default_factory=dict)
    results: list[SlotExecutionResult] = Field(default_factory=list)
    duration_sec: float = 0.0
    dry_run: bool = False
    username: str = "unknown"
    hostname: str = "unknown"


class State(StateModel):
    schema_version: int = 1
    created_at: str | None = None
    updated_at: str | None = None
    last_robot_name: str = "Sparkle"
    last_port: str = ""
    current_slots: dict[int, StateSlotEntry] = Field(default_factory=dict)
    history: list[ExecutionRecord] = Field(default_factory=list)

    @field_validator("current_slots", mode="before")
    @classmethod
    def normalize_current_slots(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("currentSlots must be a mapping")
        return {int(slot): entry for slot, entry in value.items()}

    @field_validator("history", mode="before")
    @classmethod
    def normalize_history(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("history must be a list")
        return value
