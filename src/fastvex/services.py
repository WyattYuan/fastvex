from __future__ import annotations

from dataclasses import dataclass

from .config_edit import replace_active_route_in_text
from .executor import RunOptions, execute_upload
from .models import Config, resolve_profile
from .project import DEFAULT_CONFIG, DEFAULT_STATE, LEGACY_CONFIG, ProjectPaths, resolve_project_paths
from .state_model import ExecutionRecord, State
from .storage import ValidationError, default_state, load_config, load_state, save_state
from .templates import DEFAULT_CONFIG_TEXT
from .toolchain import ToolchainCache, get_toolchain_env, resolve_toolchain, save_toolchain


@dataclass(frozen=True)
class InitReport:
    paths: ProjectPaths
    config_created: bool
    state_created: bool
    config_exists: bool
    state_exists: bool
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
class UploadRequest:
    slots: str | None = None
    group: str | None = None
    all_enabled: bool = False
    robot_name: str | None = None
    port: str | None = None
    clean: bool = False
    quiet: bool = False
    dry_run: bool = False
    yes: bool = False


@dataclass(frozen=True)
class UploadReport:
    paths: ProjectPaths
    config: Config
    slots: list[int]
    execution: ExecutionRecord | None
    failed_slots: list[int]
    aborted: bool = False


@dataclass(frozen=True)
class RouteReport:
    paths: ProjectPaths
    config: Config


@dataclass(frozen=True)
class RouteSetReport:
    paths: ProjectPaths
    route_set: str
    old_key: str
    new_key: str
    changed: bool


@dataclass(frozen=True)
class ToolchainReport:
    cache: ToolchainCache
    rediscovered: bool


def parse_slot_expr(expr: str) -> list[int]:
    values: list[int] = []
    for token in expr.replace(",", " ").split():
        slot = int(token)
        if slot < 1 or slot > 8:
            raise ValidationError(f"slot out of range: {slot}")
        values.append(slot)
    return sorted(set(values))


def resolve_slots(request: UploadRequest, config: Config) -> list[int]:
    if request.all_enabled:
        return sorted(config.slots.keys())

    if request.group:
        if request.group not in config.groups:
            raise ValidationError(f"unknown group: {request.group}")
        return config.groups[request.group]

    if request.slots:
        return parse_slot_expr(request.slots)

    return []


def init_project(config: str | None = None, state: str | None = None) -> InitReport:
    paths = resolve_project_paths(config=config or DEFAULT_CONFIG, state=state or DEFAULT_STATE, require_config=False)
    legacy_config = paths.root / LEGACY_CONFIG

    config_exists = paths.config.exists()
    state_exists = paths.state.exists()
    legacy_config_exists = paths.config.name == DEFAULT_CONFIG and legacy_config.exists()

    config_created = False
    if not config_exists and not legacy_config_exists:
        paths.config.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
        config_created = True

    state_created = False
    if not state_exists:
        save_state(paths.state, default_state())
        state_created = True

    return InitReport(
        paths=paths,
        config_created=config_created,
        state_created=state_created,
        config_exists=config_exists,
        state_exists=state_exists,
        legacy_config_exists=legacy_config_exists,
    )


def show_project(config: str | None = None, state: str | None = None) -> ShowReport:
    paths = resolve_project_paths(config=config, state=state)
    return ShowReport(paths=paths, config=load_config(paths.config), state=load_state(paths.state))


def validate_project(config: str | None = None, state: str | None = None) -> ValidationReport:
    paths = resolve_project_paths(config=config, state=state)
    loaded_config = load_config(paths.config)
    load_state(paths.state)

    warnings: list[str] = []
    for slot, binding in loaded_config.slots.items():
        role = loaded_config.roles[binding.role_id]
        if not role.enabled:
            warnings.append(f"slot {slot} references disabled role {binding.role_id}")

        resolved = resolve_profile(loaded_config, slot)
        if not resolved.enabled:
            warnings.append(
                f"slot {slot} resolves to disabled route "
                f"{resolved.route_set}:{resolved.route_key}"
            )

    return ValidationReport(paths=paths, warnings=warnings)


def get_history(config: str | None = None, state: str | None = None) -> HistoryReport:
    paths = resolve_project_paths(config=config, state=state)
    return HistoryReport(paths=paths, state=load_state(paths.state))


def clean_history(
    config: str | None = None,
    state: str | None = None,
    *,
    keep: int = 10,
) -> HistoryCleanReport:
    paths = resolve_project_paths(config=config, state=state)
    loaded_state = load_state(paths.state)
    history = list(loaded_state.history)
    if len(history) <= keep:
        return HistoryCleanReport(paths=paths, removed_count=0, kept_count=len(history), state=loaded_state)

    removed = len(history) - keep
    loaded_state.history = history[-keep:]
    save_state(paths.state, loaded_state)
    return HistoryCleanReport(paths=paths, removed_count=removed, kept_count=keep, state=loaded_state)


def plan_upload(
    request: UploadRequest,
    config: str | None = None,
    state: str | None = None,
) -> tuple[ProjectPaths, Config, State, list[int], str, str]:
    paths = resolve_project_paths(config=config, state=state)
    loaded_config = load_config(paths.config)
    loaded_state = load_state(paths.state)
    slots = resolve_slots(request, loaded_config)
    if not slots:
        raise ValidationError("no target slots selected; use --slots / --group / --all-enabled")

    robot_name = request.robot_name or loaded_config.defaults.robot_name or loaded_state.last_robot_name or "Sparkle"
    port = request.port if request.port is not None else (loaded_state.last_port or loaded_config.defaults.port or "")
    return paths, loaded_config, loaded_state, slots, robot_name, port


def upload_slots(
    request: UploadRequest,
    config: str | None = None,
    state: str | None = None,
) -> UploadReport:
    paths, loaded_config, loaded_state, slots, robot_name, port = plan_upload(request, config, state)
    toolchain = resolve_toolchain()
    toolchain_env = get_toolchain_env(toolchain)
    execution = execute_upload(
        project_root=paths.root,
        config=loaded_config,
        state=loaded_state,
        options=RunOptions(
            slots=slots,
            robot_name=robot_name,
            port=port,
            clean=request.clean,
            quiet=request.quiet,
            dry_run=request.dry_run,
            yes=request.yes,
        ),
        toolchain_env=toolchain_env,
    )
    save_state(paths.state, loaded_state)

    failed = [result.slot for result in execution.results if not (result.build.ok and result.upload.ok)]
    return UploadReport(
        paths=paths,
        config=loaded_config,
        slots=slots,
        execution=execution,
        failed_slots=failed,
    )


def show_routes(config: str | None = None, state: str | None = None) -> RouteReport:
    paths = resolve_project_paths(config=config, state=state)
    return RouteReport(paths=paths, config=load_config(paths.config))


def set_route(
    route_set: str,
    route_key: str,
    config: str | None = None,
    state: str | None = None,
) -> RouteSetReport:
    paths = resolve_project_paths(config=config, state=state)
    loaded_config = load_config(paths.config)

    route_set_key = route_set.strip().lower()
    route_key = route_key.strip()

    if route_set_key not in loaded_config.routes:
        raise ValidationError(f"unknown route set: {route_set_key}")
    if route_key not in loaded_config.routes[route_set_key]:
        keys = ", ".join(loaded_config.routes[route_set_key].keys())
        raise ValidationError(
            f"unknown route key '{route_key}' for set '{route_set_key}', choices: {keys}"
        )

    old_key = loaded_config.active_route[route_set_key]
    if old_key == route_key:
        return RouteSetReport(
            paths=paths,
            route_set=route_set_key,
            old_key=old_key,
            new_key=route_key,
            changed=False,
        )

    raw = paths.config.read_text(encoding="utf-8")
    updated = replace_active_route_in_text(raw, route_set_key, route_key)
    paths.config.write_text(updated, encoding="utf-8")

    return RouteSetReport(
        paths=paths,
        route_set=route_set_key,
        old_key=old_key,
        new_key=route_key,
        changed=True,
    )


def show_toolchain(rescan: bool = False) -> ToolchainReport:
    from .toolchain import _global_toolchain_path

    old_cache = resolve_toolchain()

    if rescan:
        cache_path = _global_toolchain_path()
        if cache_path.is_file():
            cache_path.unlink()
        old_cache = ToolchainCache()

    new_cache = resolve_toolchain()
    rediscovered = old_cache.pros_path != new_cache.pros_path
    return ToolchainReport(cache=new_cache, rediscovered=rediscovered)
