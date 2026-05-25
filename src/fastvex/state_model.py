from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Profile


class StateModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class StepRecord(StateModel):
    ok: bool = False
    command: list[str] = Field(default_factory=list)
    duration_sec: float = Field(0.0, alias="durationSec")
    returncode: int | None = None
    output: str = ""
    error: str = ""


class StateSlotEntry(StateModel):
    profile_id: str = Field(alias="profileId")
    role_id: str = Field(alias="roleId")
    route_set: str = Field(alias="routeSet")
    route_key: str = Field(alias="routeKey")
    mode: str
    route: int
    route_name: str = Field(alias="routeName")
    label: str
    final_name: str = Field(alias="finalName")
    uploaded_at: str = Field(alias="uploadedAt")

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
    profile_id: str = Field("", alias="profileId")
    role_id: str = Field("", alias="roleId")
    route_set: str = Field("", alias="routeSet")
    route_key: str = Field("", alias="routeKey")
    mode: str = ""
    route: int = 0
    final_name: str = Field("", alias="finalName")
    build: StepRecord = Field(default_factory=StepRecord)
    upload: StepRecord = Field(default_factory=StepRecord)
    dry_run: bool = Field(False, alias="dryRun")


class ExecutionRecord(StateModel):
    started_at: str = Field("", alias="startedAt")
    ended_at: str = Field("", alias="endedAt")
    status: str = "unknown"
    robot_name: str = Field("", alias="robotName")
    port: str = ""
    requested_slots: list[int] = Field(default_factory=list, alias="requestedSlots")
    before_snapshot: dict[int, StateSlotEntry] = Field(default_factory=dict, alias="beforeSnapshot")
    after_snapshot: dict[int, StateSlotEntry] = Field(default_factory=dict, alias="afterSnapshot")
    results: list[SlotExecutionResult] = Field(default_factory=list)
    duration_sec: float = Field(0.0, alias="durationSec")
    dry_run: bool = Field(False, alias="dryRun")
    username: str = "unknown"
    hostname: str = "unknown"


class State(StateModel):
    schema_version: int = Field(1, alias="schemaVersion")
    created_at: str | None = Field(None, alias="createdAt")
    updated_at: str | None = Field(None, alias="updatedAt")
    last_robot_name: str = Field("Sparkle", alias="lastRobotName")
    last_port: str = Field("", alias="lastPort")
    current_slots: dict[int, StateSlotEntry] = Field(default_factory=dict, alias="currentSlots")
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
