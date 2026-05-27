"""Slot resolution and build-arg logic.

This module owns the computation that turns a Config + slot number into
a fully-resolved, ready-to-build ResolvedSlot, together with all helpers
that operate on build arguments and program names.

Schema definitions (Pydantic models) live in models.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from string import Formatter

from .models import BuildArg, Config

# ── Program-name constants ────────────────────────────────────────────────────

PROGRAM_NAME_LIMIT = 32
PROGRAM_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
WHITESPACE_RE = re.compile(r"\s+")
DASH_RE = re.compile(r"-+")


# ── ResolvedSlot ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResolvedSlot:
    slot: int
    profile: str
    alliance: str
    route: str
    build_args: list[BuildArg]
    program_name: str

    @property
    def build_key(self) -> str:
        return f"{self.profile}:{self.route}"


# ── Build-arg helpers ─────────────────────────────────────────────────────────


def merge_build_args(
    profile_args: dict[str, str],
    route_args: dict[str, str],
) -> tuple[list[BuildArg], list[str]]:
    ordered: list[BuildArg] = []
    positions: dict[str, int] = {}
    warnings: list[str] = []

    for name, value in profile_args.items():
        positions[name] = len(ordered)
        ordered.append(BuildArg(name=name, value=value))

    for name, value in route_args.items():
        if name in positions:
            warnings.append(f"route buildArgs overrides profile buildArg '{name}'")
            idx = positions.pop(name)
            ordered.pop(idx)
            positions = {arg.name: i for i, arg in enumerate(ordered)}
        positions[name] = len(ordered)
        ordered.append(BuildArg(name=name, value=value))

    return ordered, warnings


def build_arg_strings(args: list[BuildArg]) -> list[str]:
    return [f"{arg.name}={arg.value}" for arg in args]


# ── Program-name helpers ──────────────────────────────────────────────────────


def clean_program_name(value: str) -> str:
    text = value.strip()
    text = WHITESPACE_RE.sub("-", text)
    text = PROGRAM_NAME_RE.sub("-", text)
    text = DASH_RE.sub("-", text).strip("-")
    if not text:
        raise ValueError("programName rendered to an empty name")
    return text


def render_program_name(config: Config, resolved: ResolvedSlot) -> str:
    values = {
        "robot": config.robot.name,
        "team": config.robot.team,
        "profile": resolved.profile,
        "alliance": resolved.alliance,
        "route": resolved.route,
        "slot": str(resolved.slot),
    }
    for _, field_name, _, _ in Formatter().parse(config.program_name.template):
        if field_name is None:
            continue
        if values.get(field_name) is None:
            raise ValueError(f"programName.template uses {{{field_name}}}, but it is not set")
    raw = config.program_name.template.format(**values)
    return clean_program_name(raw)


# ── Slot resolution ───────────────────────────────────────────────────────────


def resolve_slot(config: Config, slot: int) -> ResolvedSlot | None:
    binding = config.slots[slot]
    if binding is None:
        return None
    profile = config.profiles[binding.profile]
    route = config.alliances[profile.alliance].routes[binding.route]
    build_args, _ = merge_build_args(profile.build_args, route.build_args)
    partial = ResolvedSlot(
        slot=slot,
        profile=binding.profile,
        alliance=profile.alliance,
        route=binding.route,
        build_args=build_args,
        program_name="",
    )
    return ResolvedSlot(
        slot=slot,
        profile=partial.profile,
        alliance=partial.alliance,
        route=partial.route,
        build_args=partial.build_args,
        program_name=render_program_name(config, partial),
    )
