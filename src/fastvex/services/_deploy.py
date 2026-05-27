"""Deploy planning and execution commands."""
from __future__ import annotations

from . import (
    DeployRequest,
    DeployPlan,
    DeployReport,
)
from ._helpers import _load_state_resilient, parse_slot_expr, validate_config
from ..resolve import ResolvedSlot, resolve_slot
from ..project import resolve_project_paths
from ..state_model import ExecutionRecord
from ..errors import ValidationError
from ..storage import load_config, load_settings, save_state


def _resolve_targets(request: DeployRequest, config) -> tuple[list[int], bool, list[str]]:
    if request.slots and request.group:
        raise ValidationError("--slots and --group are mutually exclusive")
    if request.slots:
        slots, warnings = parse_slot_expr(request.slots)
        if not slots:
            raise ValidationError("no target slots selected; use --slots or --group")
        return slots, False, warnings
    if request.group:
        if request.group not in config.slot_groups:
            raise ValidationError(f"unknown slot group: {request.group}")
        slots: list[int] = []
        warnings: list[str] = []
        seen: set[int] = set()
        for slot in config.slot_groups[request.group]:
            if slot in seen:
                warnings.append(f"duplicate slot ignored: {slot}")
                continue
            seen.add(slot)
            slots.append(slot)
        return slots, True, warnings
    raise ValidationError("no target slots selected; use --slots or --group")


def plan_deploy(
    request: DeployRequest,
    config: str | None = None,
    state: str | None = None,
) -> DeployPlan:
    paths = resolve_project_paths(config=config, state=state)
    loaded_config = load_config(paths.config)
    loaded_state = _load_state_resilient(paths.state)
    settings, settings_warnings = load_settings(paths.settings)

    target_slots, indirect, target_warnings = _resolve_targets(request, loaded_config)
    deploy_slots: list[ResolvedSlot] = []
    skipped_empty_slots: list[int] = []
    for slot in target_slots:
        resolved = resolve_slot(loaded_config, slot)
        if resolved is None:
            if indirect:
                skipped_empty_slots.append(slot)
                continue
            raise ValidationError(f"slot {slot} is empty")
        deploy_slots.append(resolved)

    if not deploy_slots:
        skipped = ", ".join(str(slot) for slot in skipped_empty_slots)
        raise ValidationError(f"no deployable slots selected; skipped empty slots: {skipped}")

    port = request.port if request.port is not None else loaded_state.last_port
    warnings = [
        *settings_warnings,
        *validate_config(loaded_config),
        *target_warnings,
    ]
    if skipped_empty_slots:
        warnings.append(
            "skipped empty slots: " + ", ".join(str(slot) for slot in skipped_empty_slots)
        )

    return DeployPlan(
        paths=paths,
        config=loaded_config,
        state=loaded_state,
        settings=settings,
        requested_slots=target_slots,
        deploy_slots=deploy_slots,
        skipped_empty_slots=skipped_empty_slots,
        warnings=warnings,
        port=port,
        indirect=indirect,
    )


def deploy_slots(
    request: DeployRequest,
    config: str | None = None,
    state: str | None = None,
) -> DeployReport:
    from ..executor import RunOptions, execute_deploy
    from ..toolchain import get_toolchain_env, resolve_toolchain

    plan = plan_deploy(request, config=config, state=state)
    if request.port is not None:
        plan.state.last_port = request.port

    toolchain = resolve_toolchain()
    toolchain_env = get_toolchain_env(toolchain)

    def checkpoint(execution: ExecutionRecord) -> None:
        plan.state.active_execution = execution
        save_state(plan.paths.state, plan.state)

    execution = execute_deploy(
        project_root=plan.paths.root,
        config=plan.config,
        state=plan.state,
        options=RunOptions(
            slots=[slot.slot for slot in plan.deploy_slots],
            port=plan.port,
            clean=request.clean,
            quiet=request.quiet,
            dry_run=request.dry_run,
            yes=request.yes,
        ),
        toolchain_env=toolchain_env,
        checkpoint=None if request.dry_run else checkpoint,
    )
    execution.skipped_empty_slots = plan.skipped_empty_slots
    if not request.dry_run:
        history = list(plan.state.history)
        history.append(execution)
        plan.state.history = history[-plan.settings.history_retention_count:]
        plan.state.active_execution = None
        save_state(plan.paths.state, plan.state)

    failed = [
        upload.slot
        for upload in execution.uploads
        if upload.status != "success" or not upload.step.ok
    ]
    return DeployReport(
        paths=plan.paths,
        config=plan.config,
        slots=[slot.slot for slot in plan.deploy_slots],
        execution=execution,
        failed_slots=failed,
    )
