from __future__ import annotations

import shutil
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .models import Config, PROGRAM_NAME_LIMIT, ResolvedSlot, merge_build_args, resolve_slot, utc_now_iso
from .project import DEFAULT_CONFIG, DEFAULT_STATE, LEGACY_CONFIG, ProjectPaths, resolve_project_paths
from .state_model import ExecutionRecord, Settings, State
from .storage import (
    ValidationError,
    default_settings,
    default_state,
    load_config,
    load_settings,
    load_state,
    load_yaml,
    save_settings,
    save_state,
)


@dataclass(frozen=True)
class InitReport:
    paths: ProjectPaths
    config_created: bool
    state_created: bool
    settings_created: bool
    gitignore_created: bool
    config_exists: bool
    state_exists: bool
    settings_exists: bool
    gitignore_exists: bool
    legacy_config_exists: bool


@dataclass(frozen=True)
class ShowReport:
    paths: ProjectPaths
    config: Config
    state: State


@dataclass(frozen=True)
class ValidationReport:
    paths: ProjectPaths
    warnings: list[str]


@dataclass(frozen=True)
class HistoryReport:
    paths: ProjectPaths
    state: State


@dataclass(frozen=True)
class HistoryCleanReport:
    paths: ProjectPaths
    removed_count: int
    kept_count: int
    state: State


@dataclass(frozen=True)
class DeployRequest:
    slots: str | None = None
    group: str | None = None
    port: str | None = None
    clean: bool = False
    quiet: bool = False
    dry_run: bool = False
    yes: bool = False


@dataclass(frozen=True)
class DeployPlan:
    paths: ProjectPaths
    config: Config
    state: State
    settings: Settings
    requested_slots: list[int]
    deploy_slots: list[ResolvedSlot]
    skipped_empty_slots: list[int]
    warnings: list[str]
    port: str
    indirect: bool


@dataclass(frozen=True)
class DeployReport:
    paths: ProjectPaths
    config: Config
    slots: list[int]
    execution: ExecutionRecord | None
    failed_slots: list[int]
    aborted: bool = False


@dataclass(frozen=True)
class ToolchainReport:
    cache: ToolchainCache
    rediscovered: bool


@dataclass(frozen=True)
class MigrateReport:
    source: Path
    output: Path
    wrote_in_place: bool
    warnings: list[str]


def _timestamp() -> str:
    return utc_now_iso().replace("-", "").replace(":", "").split("+", 1)[0].replace("T", "-")


def _backup(path: Path, *, tag: str = "backup") -> None:
    if not path.exists():
        return
    suffix = "".join(path.suffixes)
    stem = path.name.removesuffix(suffix) if suffix else path.name
    backup = path.with_name(f"{stem}.{tag}.{_timestamp()}{suffix}")
    shutil.copy2(path, backup)


def _backup_v1(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(f"{path.stem}.v1.backup.{_timestamp()}{path.suffix}")
    shutil.copy2(path, backup)


def init_project(
    config: str | None = None,
    state: str | None = None,
    *,
    force: bool = False,
) -> InitReport:
    from .templates import DEFAULT_CONFIG_TEXT, DEFAULT_LOCAL_GITIGNORE_TEXT

    paths = resolve_project_paths(config=config or DEFAULT_CONFIG, state=state or DEFAULT_STATE, require_config=False)
    legacy_config = paths.root / LEGACY_CONFIG

    config_exists = paths.config.exists()
    state_exists = paths.state.exists()
    settings_exists = paths.settings.exists()
    gitignore_exists = paths.local_gitignore.exists()
    legacy_config_exists = paths.config.name == DEFAULT_CONFIG and legacy_config.exists()

    if force:
        for path in [paths.config, paths.state, paths.settings, paths.local_gitignore]:
            _backup(path)

    config_created = False
    if force or (not config_exists and not legacy_config_exists):
        paths.config.parent.mkdir(parents=True, exist_ok=True)
        paths.config.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
        config_created = True

    paths.local_gitignore.parent.mkdir(parents=True, exist_ok=True)

    state_created = False
    if force or not state_exists:
        save_state(paths.state, default_state())
        state_created = True

    settings_created = False
    if force or not settings_exists:
        save_settings(paths.settings, default_settings())
        settings_created = True

    gitignore_created = False
    if force or not gitignore_exists:
        paths.local_gitignore.write_text(DEFAULT_LOCAL_GITIGNORE_TEXT, encoding="utf-8")
        gitignore_created = True

    return InitReport(
        paths=paths,
        config_created=config_created,
        state_created=state_created,
        settings_created=settings_created,
        gitignore_created=gitignore_created,
        config_exists=config_exists,
        state_exists=state_exists,
        settings_exists=settings_exists,
        gitignore_exists=gitignore_exists,
        legacy_config_exists=legacy_config_exists,
    )


def parse_slot_expr(expr: str) -> tuple[list[int], list[str]]:
    values: list[int] = []
    warnings: list[str] = []
    seen: set[int] = set()
    for token in expr.replace(",", " ").split():
        slot = int(token)
        if slot < 1 or slot > 8:
            raise ValidationError(f"slot out of range: {slot}")
        if slot in seen:
            warnings.append(f"duplicate slot ignored: {slot}")
            continue
        seen.add(slot)
        values.append(slot)
    return values, warnings


def validate_config(config: Config) -> list[str]:
    warnings: list[str] = []
    for profile_key, profile in config.profiles.items():
        if not profile.build_args:
            warnings.append(f"profile '{profile_key}' has empty buildArgs")

    for alliance_key, alliance in config.alliances.items():
        for route_key, route in alliance.routes.items():
            if not route.build_args:
                warnings.append(f"route '{alliance_key}:{route_key}' has empty buildArgs")

    seen_pairs: dict[tuple[str, str], int] = {}
    for slot in range(1, 9):
        resolved = resolve_slot(config, slot)
        if resolved is None:
            continue
        profile = config.profiles[resolved.profile]
        route = config.alliances[profile.alliance].routes[resolved.route]
        _, merge_warnings = merge_build_args(profile.build_args, route.build_args)
        warnings.extend(f"slot {slot}: {warning}" for warning in merge_warnings)
        if len(resolved.program_name) > PROGRAM_NAME_LIMIT:
            warnings.append(
                f"slot {slot} programName '{resolved.program_name}' exceeds {PROGRAM_NAME_LIMIT} chars"
            )
        pair = (resolved.profile, resolved.route)
        if pair in seen_pairs:
            warnings.append(
                f"slot {slot} duplicates profile+route from slot {seen_pairs[pair]}: "
                f"{resolved.profile}:{resolved.route}"
            )
        else:
            seen_pairs[pair] = slot

    all_group = config.slot_groups.get("all")
    if all_group != list(range(1, 9)):
        warnings.append("slotGroups.all is missing or not complete 1..8")

    return warnings


def _load_state_resilient(path: Path) -> State:
    try:
        return load_state(path)
    except ValidationError:
        _backup(path, tag="corrupt")
        state = default_state()
        save_state(path, state)
        return state


def show_project(config: str | None = None, state: str | None = None) -> ShowReport:
    paths = resolve_project_paths(config=config, state=state)
    return ShowReport(paths=paths, config=load_config(paths.config), state=_load_state_resilient(paths.state))


def validate_project(config: str | None = None, state: str | None = None) -> ValidationReport:
    paths = resolve_project_paths(config=config, state=state)
    loaded_config = load_config(paths.config)
    _, settings_warnings = load_settings(paths.settings)
    _load_state_resilient(paths.state)
    warnings = [*settings_warnings, *validate_config(loaded_config)]
    return ValidationReport(paths=paths, warnings=warnings)


def get_history(config: str | None = None, state: str | None = None) -> HistoryReport:
    paths = resolve_project_paths(config=config, state=state)
    load_config(paths.config)
    return HistoryReport(paths=paths, state=_load_state_resilient(paths.state))


def clean_history(
    config: str | None = None,
    state: str | None = None,
    *,
    keep: int = 10,
) -> HistoryCleanReport:
    paths = resolve_project_paths(config=config, state=state)
    load_config(paths.config)
    loaded_state = _load_state_resilient(paths.state)
    history = list(loaded_state.history)
    if len(history) <= keep:
        return HistoryCleanReport(paths=paths, removed_count=0, kept_count=len(history), state=loaded_state)

    removed = len(history) - keep
    loaded_state.history = history[-keep:]
    save_state(paths.state, loaded_state)
    return HistoryCleanReport(paths=paths, removed_count=removed, kept_count=keep, state=loaded_state)


def _resolve_targets(request: DeployRequest, config: Config) -> tuple[list[int], bool, list[str]]:
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
    from .executor import RunOptions, execute_deploy
    from .toolchain import get_toolchain_env, resolve_toolchain

    plan = plan_deploy(request, config=config, state=state)
    if request.port is not None:
        plan.state.last_port = request.port

    toolchain = resolve_toolchain()
    toolchain_env = get_toolchain_env(toolchain)
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
    )
    execution.skipped_empty_slots = plan.skipped_empty_slots
    if not request.dry_run:
        history = list(plan.state.history)
        history.append(execution)
        plan.state.history = history[-plan.settings.history_retention_count:]
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
        raw_route = raw_binding.get("route") or raw_active.get(old_route_set)
        if raw_route is None:
            raise ValidationError(f"v1 slot {slot} has no route and activeRoute.{old_route_set} is missing")
        route_key = route_key_map.get((old_route_set, str(raw_route)), _to_lower_camel(raw_route))
        slots[slot] = {
            "profile": role_map[old_role],
            "route": route_key,
        }

    slot_groups: dict[str, list[int]] = {"all": list(range(1, 9))}
    for old_group, raw_group_slots in raw_groups.items():
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


def show_toolchain(rescan: bool = False) -> ToolchainReport:
    from .toolchain import ToolchainCache, _global_toolchain_path, invalidate_toolchain_cache, resolve_toolchain

    old_cache = resolve_toolchain()

    if rescan:
        invalidate_toolchain_cache()
        cache_path = _global_toolchain_path()
        if cache_path.is_file():
            cache_path.unlink()
        old_cache = ToolchainCache()

    new_cache = resolve_toolchain()
    rediscovered = old_cache.pros_path != new_cache.pros_path
    return ToolchainReport(cache=new_cache, rediscovered=rediscovered)
