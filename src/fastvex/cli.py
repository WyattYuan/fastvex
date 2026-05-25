from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import click
import typer

from . import __version__
from .display import (
    print_dashboard,
    print_execution_result,
    print_history,
    print_show,
    print_upload_plan,
)
from .services import (
    HistoryCleanReport,
    ToolchainReport,
    UploadRequest,
    clean_history,
    get_history,
    init_project,
    plan_upload,
    set_route,
    show_project,
    show_routes,
    show_toolchain,
    upload_slots,
    validate_project,
)
from .storage import ValidationError
from .theme import FAIL, INFO, OK, WARN, confirm, console, err_console

CommonConfig = Annotated[str | None, typer.Option("--config", help="Config file path.")]
CommonState = Annotated[str | None, typer.Option("--state", help="State file path.")]

app = typer.Typer(
    name="fastvex",
    help="Fast VEX slot-oriented build/upload manager.",
    invoke_without_command=True,
)
history_app = typer.Typer(help="Show or clean history.")
route_app = typer.Typer(help="Show or set active route by route set.")
app.add_typer(history_app, name="history")
app.add_typer(route_app, name="route")


def _ctx_options(ctx: typer.Context, config: str | None, state: str | None) -> dict[str, str | None]:
    obj = ctx.obj or {}
    return {
        "config": config if config is not None else obj.get("config"),
        "state": state if state is not None else obj.get("state"),
    }


def _print_legacy_warning(legacy_config: bool, config_path: object) -> None:
    if legacy_config:
        console.print(f"  [yellow]{WARN} using legacy config name:[/yellow] {config_path}")


def _finish(code: int) -> None:
    if code:
        raise typer.Exit(code)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"fastvex {__version__}")
        raise typer.Exit()


def _upload_request(
    *,
    slots: str | None = None,
    group: str | None = None,
    all_enabled: bool = False,
    robot_name: str | None = None,
    port: str | None = None,
    clean: bool = False,
    quiet: bool = False,
    dry_run: bool = False,
    yes: bool = False,
) -> UploadRequest:
    return UploadRequest(
        slots=slots,
        group=group,
        all_enabled=all_enabled,
        robot_name=robot_name,
        port=port,
        clean=clean,
        quiet=quiet,
        dry_run=dry_run,
        yes=yes,
    )


def run_default_interactive(config: str | None = None, state: str | None = None) -> int:
    report = show_project(config=config, state=state)
    _print_legacy_warning(report.paths.legacy_config, report.paths.config)
    print_dashboard(report.config, report.state)

    console.print("  [bold cyan]Target[/bold cyan]  [dim]1,3 | group:all-enabled | all | q[/dim]")

    raw = console.input("  [cyan]target[/cyan]> ").strip()
    if not raw or raw.lower() in {"q", "quit", "exit"}:
        console.print("\n  [blue]bye[/blue]\n")
        return 0

    request = _upload_request()
    if raw.lower() == "all":
        request = _upload_request(all_enabled=True)
    elif raw.lower().startswith("group:"):
        request = _upload_request(group=raw.split(":", 1)[1].strip())
    else:
        request = _upload_request(slots=raw)

    planned = plan_upload(request, config=config, state=state)
    paths, loaded_config, _, slots, _, _ = planned
    _print_legacy_warning(paths.legacy_config, paths.config)
    print_upload_plan(loaded_config, slots)
    if not confirm(
        "  [yellow]Continue upload?[/yellow] [[green]Y[/green]/[red]n[/red]] (Enter for 'Y'): ",
        default_yes=True,
    ):
        console.print(f"\n  [yellow]{WARN} aborted[/yellow]\n")
        return 0

    report = upload_slots(request, config=config, state=state)
    if report.execution:
        print_execution_result(report.execution)
    return 1 if report.failed_slots else 0


@app.callback()
def root(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
    version: Annotated[
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True, help="Show version.")
    ] = None,
) -> None:
    ctx.obj = {"config": config, "state": state}
    if ctx.invoked_subcommand is None:
        _finish(run_default_interactive(config=config, state=state))


@app.command("init")
def init_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    options = _ctx_options(ctx, config, state)
    report = init_project(**options)

    if report.config_exists:
        console.print(f"  [cyan]config exists:[/cyan] {report.paths.config}")
    elif report.legacy_config_exists:
        console.print(f"  [yellow]{WARN} legacy config exists:[/yellow] {report.paths.root / 'vex_upload_config.yaml'}")
        console.print("  [dim]fastvex init will not migrate or overwrite configs.[/dim]")
    elif report.config_created:
        console.print(f"  [green]created config:[/green] {report.paths.config}")

    if report.state_exists:
        console.print(f"  [cyan]state exists:[/cyan] {report.paths.state}")
    elif report.state_created:
        console.print(f"  [green]created state:[/green] {report.paths.state}")

    console.print(f"\n  [bold green]{OK} init ok[/bold green]\n")


@app.command("show")
def show_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
    full: Annotated[bool, typer.Option("--full", help="Show full history.")] = False,
) -> None:
    report = show_project(**_ctx_options(ctx, config, state))
    _print_legacy_warning(report.paths.legacy_config, report.paths.config)
    print_show(report.config, report.state, history_limit=None if full else 3)


@app.command("validate")
def validate_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    report = validate_project(**_ctx_options(ctx, config, state))
    _print_legacy_warning(report.paths.legacy_config, report.paths.config)
    for warning in report.warnings:
        console.print(f"  {WARN} {warning}")
    console.print(f"\n  [bold green]{OK} validate ok[/bold green]\n")


@app.command("toolchain")
def toolchain_command(
    rescan: Annotated[bool, typer.Option("--rescan", help="Force re-scan, ignore cache.")] = False,
) -> None:
    report: ToolchainReport = show_toolchain(rescan=rescan)

    if not report.cache.pros_path:
        err_console.print(f"  [yellow]{WARN} PROS not found[/yellow]")
        err_console.print("  [dim]Searched via 'which pros' — run from PROS Terminal first to cache the path.[/dim]")
        _finish(1)
        return

    status = "rescanned" if report.rediscovered else "cached"
    console.print(f"  [green]{OK} PROS found ({status}):[/green]")
    console.print(f"    path: {report.cache.pros_path}")
    if report.cache.discovered_at:
        console.print(f"    cached: {report.cache.discovered_at}")


@app.command("upload")
def upload_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
    slots: Annotated[str | None, typer.Option("--slots", help="Slot list, e.g. '1,3,5'.")] = None,
    group: Annotated[str | None, typer.Option("--group", help="Group name defined in config.")] = None,
    all_enabled: Annotated[
        bool,
        typer.Option("--all-enabled", help="Target all configured slots."),
    ] = False,
    robot_name: Annotated[str | None, typer.Option("--robot-name", help="Override robot name.")] = None,
    port: Annotated[str | None, typer.Option("--port", help="Override port. Empty means auto.")] = None,
    clean: Annotated[bool, typer.Option("--clean", help="Run make clean before build.")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help="Capture build/upload output.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Plan without build/upload.")] = False,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirm prompt.")] = False,
) -> None:
    options = _ctx_options(ctx, config, state)
    request = _upload_request(
        slots=slots,
        group=group,
        all_enabled=all_enabled,
        robot_name=robot_name,
        port=port,
        clean=clean,
        quiet=quiet,
        dry_run=dry_run,
        yes=yes,
    )
    paths, loaded_config, _, selected_slots, _, _ = plan_upload(request, **options)
    _print_legacy_warning(paths.legacy_config, paths.config)
    print_upload_plan(loaded_config, selected_slots)

    if not yes and not dry_run:
        if not confirm(
            "  [yellow]Continue upload?[/yellow] [[green]Y[/green]/[red]n[/red]] (Enter for 'Y'): ",
            default_yes=True,
        ):
            console.print(f"\n  [yellow]{WARN} aborted[/yellow]\n")
            return

    report = upload_slots(request, **options)
    if report.execution:
        print_execution_result(report.execution)
    _finish(1 if report.failed_slots else 0)


@history_app.callback()
def history_root(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    parent = ctx.parent.obj if ctx.parent and ctx.parent.obj else {}
    ctx.obj = {
        "config": config if config is not None else parent.get("config"),
        "state": state if state is not None else parent.get("state"),
    }


@history_app.command("show")
def history_show_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Number of recent entries to show.")] = None,
) -> None:
    report = get_history(**_ctx_options(ctx, config, state))
    _print_legacy_warning(report.paths.legacy_config, report.paths.config)
    console.print()
    if not report.state.history:
        console.print("  [dim](empty)[/dim]")
    else:
        print_history(report.state.history, limit=limit)


@history_app.command("clean")
def history_clean_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
    keep: Annotated[int, typer.Option("--keep", help="Number of entries to keep.")] = 10,
) -> None:
    report: HistoryCleanReport = clean_history(**_ctx_options(ctx, config, state), keep=keep)
    _print_legacy_warning(report.paths.legacy_config, report.paths.config)
    if report.removed_count == 0:
        console.print(f"  [dim]history has {report.kept_count} entries, no cleanup needed (keep={keep})[/dim]")
    else:
        console.print(
            f"  [green]{OK} cleaned[/green] {report.removed_count} "
            f"[dim]old entries, kept last[/dim] {report.kept_count}"
        )


@route_app.callback()
def route_root(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    parent = ctx.parent.obj if ctx.parent and ctx.parent.obj else {}
    ctx.obj = {
        "config": config if config is not None else parent.get("config"),
        "state": state if state is not None else parent.get("state"),
    }


@route_app.command("show")
def route_show_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    from rich.text import Text
    from .theme import role_tone

    report = show_routes(**_ctx_options(ctx, config, state))
    _print_legacy_warning(report.paths.legacy_config, report.paths.config)
    loaded_config = report.config

    console.print()
    route_items: list[Text] = []
    for route_set in sorted(loaded_config.active_route.keys()):
        color, _ = role_tone(route_set, "COMP")
        key = loaded_config.active_route[route_set]
        item = Text()
        item.append(route_set, style=f"bold {color}")
        item.append(":")
        item.append(key, style=color)
        route_items.append(item)

    console.print("  [bold cyan]Active Routes[/bold cyan]")
    console.print(Text("  ").append(Text("   ").join(route_items)))
    console.print()

    console.print("  [bold cyan]Available Routes[/bold cyan]")
    for route_set in sorted(loaded_config.routes.keys()):
        color, _ = role_tone(route_set, "COMP")
        active_key = loaded_config.active_route.get(route_set)

        header = Text("\n  ")
        header.append(route_set, style=f"bold {color}")
        console.print(header)
        for key, opt in loaded_config.routes[route_set].items():
            is_active = key == active_key
            marker = f"[green]{OK}[/green] " if is_active else "    "
            active_tag = " [green](active)[/green]" if is_active else ""
            console.print(
                f"    {marker}[cyan]{key}[/cyan]  "
                f"route={opt.route}  routeName={opt.route_name}{active_tag}"
            )
    console.print()


@route_app.command("set")
def route_set_command(
    ctx: typer.Context,
    route_set: str,
    route_key: str,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    from rich.text import Text
    from .theme import role_tone

    report = set_route(route_set, route_key, **_ctx_options(ctx, config, state))
    _print_legacy_warning(report.paths.legacy_config, report.paths.config)
    if not report.changed:
        console.print(f"\n  [dim]{INFO} route unchanged:[/dim] {report.route_set}={report.new_key}\n")
        return

    color, _ = role_tone(report.route_set, "COMP")
    msg = Text("\n  ")
    msg.append(f"{OK} updated active route: ", style="bold green")
    msg.append(f"{report.route_set} ", style=f"bold {color}")
    msg.append(f"{report.old_key} ", style="dim")
    msg.append("→ ", style="cyan")
    msg.append(f"{report.new_key}\n", style=f"bold {color}")
    console.print(msg)


def _prog_name() -> str:
    return Path(sys.argv[0]).stem or "fastvex"


def main(argv: list[str] | None = None, prog_name: str | None = None) -> int:
    try:
        app(args=argv, prog_name=prog_name or _prog_name(), standalone_mode=False)
        return 0
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except ValidationError as exc:
        err_console.print(f"\n  [bold red]{FAIL} validation error:[/bold red] {exc}\n")
        return 2
    except KeyboardInterrupt:
        err_console.print(f"\n  [yellow]{WARN} interrupted[/yellow]\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
