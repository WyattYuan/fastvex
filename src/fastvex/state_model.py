from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from .models import BuildArg
from .resolve import ResolvedSlot


class StateModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class Settings(StateModel):
    history_retention_count: int = 10


class StepRecord(StateModel):
    ok: bool = False
    command: list[str] = Field(default_factory=list)
    duration_sec: float = 0.0
    returncode: int | None = None
    output: str = ""
    error: str = ""


class BuildSignature(StateModel):
    profile: str
    route: str
    build_args: list[BuildArg] = Field(default_factory=list)

    @classmethod
    def from_slot(cls, slot: ResolvedSlot) -> BuildSignature:
        return cls(profile=slot.profile, route=slot.route, build_args=slot.build_args)


class StateSlotEntry(StateModel):
    profile: str
    alliance: str
    route: str
    program_name: str
    uploaded_at: str

    @classmethod
    def from_slot(cls, slot: ResolvedSlot, timestamp: str) -> StateSlotEntry:
        return cls(
            profile=slot.profile,
            alliance=slot.alliance,
            route=slot.route,
            program_name=slot.program_name,
            uploaded_at=timestamp,
        )


class BuildRecord(StateModel):
    id: str
    signature: BuildSignature
    step: StepRecord = Field(default_factory=StepRecord)


class UploadRecord(StateModel):
    slot: int
    build_id: str
    program_name: str
    status: str = "pending"
    reason: str = ""
    step: StepRecord = Field(default_factory=StepRecord)


class ExecutionRecord(StateModel):
    started_at: str = ""
    ended_at: str = ""
    status: str = "unknown"
    port: str = ""
    requested_slots: list[int] = Field(default_factory=list)
    skipped_empty_slots: list[int] = Field(default_factory=list)
    builds: list[BuildRecord] = Field(default_factory=list)
    uploads: list[UploadRecord] = Field(default_factory=list)
    duration_sec: float = 0.0
    dry_run: bool = False
    username: str = "unknown"
    hostname: str = "unknown"


class State(StateModel):
    schema_version: int = 2
    created_at: str | None = None
    updated_at: str | None = None
    last_port: str = ""
    last_build_signature: BuildSignature | None = None
    active_execution: ExecutionRecord | None = None
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
