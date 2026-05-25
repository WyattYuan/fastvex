from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .display import print_show, print_history, print_upload_plan, print_execution_result
from .executor import RunOptions, execute_upload
from .models import resolve_profile
from .storage import ValidationError, load_config, load_state, save_state
from .templates import DEFAULT_CONFIG_TEXT
from .theme import OK, FAIL, WARN, INFO, confirm, console

DEFAULT_CONFIG = "fastvex.yaml"
LEGACY_CONFIG = "vex_upload_config.yaml"
DEFAULT_STATE = ".fastvex/state.json"


def rprint(*args, **kwargs) -> None:
    """Rich-aware print: uses console.print unless an explicit file= is given."""
    file = kwargs.pop("file", None)
    if file is not None:
        kwargs.setdefault("sep", " ")
        kwargs.setdefault("end", "\n")
        kwargs.setdefault("flush", False)
        print(*args, file=file, **kwargs)
    else:
        console.print(*args, **kwargs)


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    config: Path
    state: Path
    legacy_config: bool = False


def _resolve_relative_to(base: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return base / path


def find_config(start: Path) -> tuple[Path, bool] | None:
    current = start.resolve()
    search_dirs = [current, *current.parents]
    for directory in search_dirs:
        candidate = directory / DEFAULT_CONFIG
        if candidate.exists():
            return candidate, False
        legacy = directory / LEGACY_CONFIG
        if legacy.exists():
            return legacy, True
    return None


def resolve_project_paths(args: argparse.Namespace, *, require_config: bool = True) -> ProjectPaths:
    config_arg = getattr(args, "config", None)
    if config_arg:
        config_path = Path(config_arg)
        if not config_path.is_absolute():
            config_path = Path.cwd() / config_path
        config_path = config_path.resolve()
        legacy_config = config_path.name == LEGACY_CONFIG
        if require_config and not config_path.exists():
            raise ValidationError(f"Config file not found: {config_path}")
    else:
        found = find_config(Path.cwd())
        if found is None:
            if require_config:
                raise ValidationError(
                    f"Config file not found. Run 'fastvex init' or pass --config {DEFAULT_CONFIG}."
                )
            config_path = (Path.cwd() / DEFAULT_CONFIG).resolve()
            legacy_config = False
        else:
            config_path, legacy_config = found

    root = config_path.parent
    state_arg = getattr(args, "state", None)
    state_path = (
        _resolve_relative_to(root, state_arg).resolve()
        if state_arg
        else (root / DEFAULT_STATE).resolve()
    )

    if legacy_config:
        rprint(f"  [yellow]{WARN} using legacy config name:[/yellow] {config_path}")

    return ProjectPaths(root=root, config=config_path, state=state_path, legacy_config=legacy_config)


def parse_slot_expr(expr: str) -> list[int]:
    values: list[int] = []
    for token in expr.replace(",", " ").split():
        n = int(token)
        if n < 1 or n > 8:
            raise ValidationError(f"slot out of range: {n}")
        values.append(n)
    return sorted(set(values))


def resolve_slots(args: argparse.Namespace, config: Any) -> list[int]:
    if getattr(args, "all_enabled", False):
        return sorted(config.slots.keys())

    group = getattr(args, "group", None)
    if group:
        if group not in config.groups:
            raise ValidationError(f"unknown group: {group}")
        return config.groups[group]

    slots_expr = getattr(args, "slots", None)
    if slots_expr:
        return parse_slot_expr(slots_expr)

    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════════════════════


def cmd_init(args: argparse.Namespace) -> int:
    root = Path.cwd().resolve()
    cfg = _resolve_relative_to(root, args.config or DEFAULT_CONFIG).resolve()
    st = _resolve_relative_to(root, args.state or DEFAULT_STATE).resolve()
    legacy_cfg = root / LEGACY_CONFIG

    if cfg.exists():
        rprint(f"  [cyan]config exists:[/cyan] {cfg}")
    else:
        if cfg.name == DEFAULT_CONFIG and legacy_cfg.exists():
            rprint(f"  [yellow]{WARN} legacy config exists:[/yellow] {legacy_cfg}")
            rprint("  [dim]fastvex init will not migrate or overwrite configs.[/dim]")
        else:
            cfg.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
            rprint(f"  [green]created config:[/green] {cfg}")

    if st.exists():
        rprint(f"  [cyan]state exists:[/cyan] {st}")
    else:
        seed = {
            "schemaVersion": 1,
            "createdAt": None,
            "updatedAt": None,
            "lastRobotName": "Sparkle",
            "lastPort": "",
            "currentSlots": {},
            "history": [],
        }
        save_state(st, seed)
        rprint(f"  [green]created state:[/green] {st}")

    rprint(f"\n  [bold green]{OK} init ok[/bold green]\n")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    paths = resolve_project_paths(args)
    config = load_config(paths.config)
    state = load_state(paths.state)
    print_show(config, state)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    paths = resolve_project_paths(args)
    config = load_config(paths.config)
    load_state(paths.state)

    warnings: list[str] = []
    for slot, binding in config.slots.items():
        role = config.roles[binding.role_id]
        if not role.enabled:
            warnings.append(f"  {WARN} slot {slot} references disabled role {binding.role_id}")

        resolved = resolve_profile(config, slot)
        if not resolved.enabled:
            warnings.append(
                f"  {WARN} slot {slot} resolves to disabled route "
                f"{resolved.route_set}:{resolved.route_key}"
            )

    for w in warnings:
        rprint(w)

    rprint(f"\n  [bold green]{OK} validate ok[/bold green]\n")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    paths = resolve_project_paths(args)
    state = load_state(paths.state)
    hist  = state.get("history", [])

    rprint()
    if not hist:
        rprint("  [dim](empty)[/dim]")
    else:
        print_history(hist)
    return 0


def cmd_history_clean(args: argparse.Namespace) -> int:
    paths = resolve_project_paths(args)
    state_path = paths.state
    state = load_state(state_path)

    keep = args.keep
    hist = list(state.get("history", []))
    if len(hist) <= keep:
        rprint(f"  [dim]history has {len(hist)} entries, no cleanup needed (keep={keep})[/dim]")
        return 0

    removed = len(hist) - keep
    state["history"] = hist[-keep:]
    save_state(state_path, state)
    rprint(f"  [green]{OK} cleaned[/green] {removed} [dim]old entries, kept last[/dim] {keep}")
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    paths = resolve_project_paths(args)
    root = paths.root
    cfg_path = paths.config
    state_path = paths.state

    config = load_config(cfg_path)
    state  = load_state(state_path)

    slots = resolve_slots(args, config)
    if not slots:
        raise ValidationError("no target slots selected; use --slots / --group / --all-enabled")

    robot_name = args.robot_name or config.defaults.robot_name or state.get("lastRobotName") or "Sparkle"
    port = args.port if args.port is not None else (state.get("lastPort") or config.defaults.port or "")

    print_upload_plan(config, slots)

    if not args.yes and not args.dry_run:
        if not confirm(
            "  [yellow]Continue upload?[/yellow] [[green]Y[/green]/[red]n[/red]] (Enter for 'Y'): ",
            default_yes=True,
        ):
            rprint(f"\n  [yellow]{WARN} aborted[/yellow]\n")
            return 0

    execution = execute_upload(
        project_root=root,
        config=config,
        state=state,
        options=RunOptions(
            slots=slots,
            robot_name=robot_name,
            port=port,
            clean=args.clean,
            quiet=args.quiet,
            dry_run=args.dry_run,
            yes=args.yes,
        ),
    )

    save_state(state_path, state)
    print_execution_result(execution)

    failed = [r for r in execution["results"] if not (r["build"]["ok"] and r["upload"]["ok"])]
    return 1 if failed else 0


def run_default_interactive(args: argparse.Namespace) -> int:
    code = cmd_show(args)
    if code != 0:
        return code

    rprint("  [bold cyan]Select upload target:[/bold cyan]")
    rprint("    [dim]slot list[/dim]  e.g. [green]1,3,5[/green]")
    rprint("    [dim]group:name[/dim]  e.g. [green]group:comp-default[/green]")
    rprint("    [dim]all[/dim]         upload all enabled slots")
    rprint("    [dim]q[/dim]           quit")
    rprint()

    raw = console.input("  [cyan]target[/cyan]> ").strip()
    if not raw or raw.lower() in {"q", "quit", "exit"}:
        rprint("\n  [blue]bye[/blue]\n")
        return 0

    # reset upload-related args before delegating to cmd_upload
    args.yes         = False
    args.dry_run     = False
    args.clean       = False
    args.quiet       = False
    args.robot_name  = None
    args.port        = None
    args.all_enabled = False
    args.group       = None
    args.slots       = None

    if raw.lower() == "all":
        args.all_enabled = True
    elif raw.lower().startswith("group:"):
        args.group = raw.split(":", 1)[1].strip()
    else:
        args.slots = raw

    return cmd_upload(args)


# ═══════════════════════════════════════════════════════════════════════════════
# Route commands
# ═══════════════════════════════════════════════════════════════════════════════


def cmd_route_show(args: argparse.Namespace) -> int:
    from .theme import role_tone

    paths = resolve_project_paths(args)
    config = load_config(paths.config)

    rprint()

    # ── Active routes row
    route_items = []
    for route_set in sorted(config.active_route.keys()):
        color, _ = role_tone(route_set, "COMP")
        key = config.active_route[route_set]
        route_items.append(f"[bold {color}]{route_set}[/bold {color}]:[{color}]{key}[/{color}]")

    rprint("  [bold cyan]Active Routes[/bold cyan]")
    rprint(f"  {'   '.join(route_items)}")
    rprint()

    # ── Available routes
    rprint("  [bold cyan]Available Routes[/bold cyan]")
    for route_set in sorted(config.routes.keys()):
        color, _ = role_tone(route_set, "COMP")
        active_key = config.active_route.get(route_set)

        rprint(f"\n  [bold {color}]{route_set}[/bold {color}]")
        for key, opt in config.routes[route_set].items():
            is_active = key == active_key
            marker = f"[green]{OK}[/green] " if is_active else "    "
            active_tag = " [green](active)[/green]" if is_active else ""
            rprint(
                f"    {marker}[cyan]{key}[/cyan]  "
                f"route={opt.route}  routeName={opt.route_name}{active_tag}"
            )
    rprint()
    return 0


def _replace_active_route_in_text(text: str, route_set: str, route_key: str) -> str:
    """Simple text-based replacement to keep YAML comments/formatting intact."""
    lines = text.splitlines()
    in_active = False
    found = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "activeRoute:":
            in_active = True
            continue
        if in_active:
            # left-indent ended → activeRoute block is over
            if stripped and not line.startswith("  "):
                break
            key_prefix = f"  {route_set}:"
            if line.startswith(key_prefix):
                lines[idx] = f"  {route_set}: {route_key}"
                found = True
                break
    if not found:
        raise ValidationError(f"failed to update activeRoute.{route_set} in config file")
    return "\n".join(lines) + "\n"


def cmd_route_set(args: argparse.Namespace) -> int:
    from .theme import role_tone

    paths = resolve_project_paths(args)
    config_path = paths.config
    config = load_config(config_path)

    route_set = str(args.route_set).strip().lower()
    route_key = str(args.route_key).strip()

    if route_set not in config.routes:
        raise ValidationError(f"unknown route set: {route_set}")
    if route_key not in config.routes[route_set]:
        keys = ", ".join(config.routes[route_set].keys())
        raise ValidationError(
            f"unknown route key '{route_key}' for set '{route_set}', "
            f"choices: {keys}"
        )

    old_key = config.active_route[route_set]
    if old_key == route_key:
        rprint(f"\n  [dim]{INFO} route unchanged:[/dim] {route_set}={route_key}\n")
        return 0

    raw     = config_path.read_text(encoding="utf-8")
    updated = _replace_active_route_in_text(raw, route_set, route_key)
    config_path.write_text(updated, encoding="utf-8")

    color, _ = role_tone(route_set, "COMP")
    rprint(
        f"\n  [bold green]{OK} updated active route:[/bold green] "
        f"[bold {color}]{route_set}[/bold {color}] [dim]{old_key}[/dim] "
        f"[cyan]→[/cyan] [bold {color}]{route_key}[/bold {color}]\n"
    )
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# Argument parser helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _add_common_args(parser: argparse.ArgumentParser, *, suppress_default: bool = False) -> None:
    default = argparse.SUPPRESS if suppress_default else None
    parser.add_argument("--config", default=default)
    parser.add_argument("--state", default=default)


def _add_history_subparsers(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    show = sub.add_parser("show", help="print recent history entries")
    _add_common_args(show, suppress_default=True)
    show.set_defaults(func=cmd_history)

    clean = sub.add_parser("clean", help="clean old history entries")
    _add_common_args(clean, suppress_default=True)
    clean.add_argument(
        "--keep", type=int, default=10,
        help="number of entries to keep (default: 10)"
    )
    clean.set_defaults(func=cmd_history_clean)


def _add_route_subparsers(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    show = sub.add_parser("show", help="show active and available routes")
    _add_common_args(show, suppress_default=True)
    show.set_defaults(func=cmd_route_show)

    set_ = sub.add_parser("set", help="set active route for a route set")
    _add_common_args(set_, suppress_default=True)
    set_.add_argument("route_set", help="route set name, e.g. red")
    set_.add_argument("route_key", help="route key, e.g. LC")
    set_.set_defaults(func=cmd_route_set)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fastvex",
        description="Fast VEX slot-oriented build/upload manager",
    )
    _add_common_args(p)

    sub = p.add_subparsers(dest="cmd", required=False)

    # simple commands
    init = sub.add_parser("init", help="initialize local files")
    _add_common_args(init, suppress_default=True)
    init.set_defaults(func=cmd_init)

    show = sub.add_parser("show", help="show slot mapping and recent history")
    _add_common_args(show, suppress_default=True)
    show.set_defaults(func=cmd_show)

    validate = sub.add_parser("validate", help="validate config and state")
    _add_common_args(validate, suppress_default=True)
    validate.set_defaults(func=cmd_validate)

    # history
    history_parser = sub.add_parser("history", help="show or clean history")
    _add_common_args(history_parser, suppress_default=True)
    _add_history_subparsers(history_parser.add_subparsers(dest="history_cmd", required=True))

    # upload
    upload = sub.add_parser("upload", help="build and upload selected slots")
    _add_common_args(upload, suppress_default=True)
    upload.add_argument("--slots", help="slot list, e.g. '1,3,5'")
    upload.add_argument("--group", help="group name defined in config")
    upload.add_argument("--all-enabled", action="store_true", help="target all slots in mapping")
    upload.add_argument("--robot-name", help="override robot name")
    upload.add_argument(
        "--port", nargs="?", const="",
        help="override port (empty for auto detect)",
    )
    upload.add_argument("--clean", action="store_true")
    upload.add_argument("--quiet", action="store_true")
    upload.add_argument("--dry-run", action="store_true")
    upload.add_argument("-y", "--yes", action="store_true", help="skip confirm prompt")
    upload.set_defaults(func=cmd_upload)

    # route
    route_parser = sub.add_parser("route", help="show or set active route by route set")
    _add_common_args(route_parser, suppress_default=True)
    _add_route_subparsers(route_parser.add_subparsers(dest="route_cmd", required=True))

    return p


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args   = parser.parse_args(argv)

    if args.cmd is None:
        args.cmd  = "interactive"
        args.func = run_default_interactive

    try:
        return int(args.func(args))
    except ValidationError as e:
        # fall back to plain print for stderr to avoid rich markup leakage
        print(f"\n  [bold red]{FAIL} validation error:[/bold red] {e}\n", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(f"\n  [yellow]{WARN} interrupted[/yellow]\n", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
