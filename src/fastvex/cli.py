from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import click
import typer

from . import __version__
from .display import (
    print_dashboard,
    print_deploy_plan,
    print_execution_result,
    print_history,
    print_show,
    print_status,
)
from .services import (
    DeployRequest,
    HistoryCleanReport,
    ToolchainReport,
    clean_history,
    deploy_slots,
    get_history,
    init_project,
    migrate_project,
    plan_deploy,
    show_project,
    show_toolchain,
    validate_project,
)
from .storage import ValidationError
from .theme import FAIL, OK, WARN, confirm, console, err_console

CommonConfig = Annotated[str | None, typer.Option("--config", help="Config file path.")]
CommonState = Annotated[str | None, typer.Option("--state", help="State file path.")]

app = typer.Typer(
    name="fastvex",
    help="Fast VEX slot-oriented deploy manager.",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
history_app = typer.Typer(
    help="Show or clean history.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(history_app, name="history")


def _ctx_options(ctx: typer.Context, config: str | None, state: str | None) -> dict[str, str | None]:
    obj = ctx.obj or {}
    return {
        "config": config if config is not None else obj.get("config"),
        "state": state if state is not None else obj.get("state"),
    }


def _finish(code: int) -> None:
    if code:
        raise typer.Exit(code)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"fastvex {__version__}")
        raise typer.Exit()


def _deploy_request(
    *,
    slots: str | None = None,
    group: str | None = None,
    port: str | None = None,
    clean: bool = False,
    quiet: bool = False,
    dry_run: bool = False,
    yes: bool = False,
) -> DeployRequest:
    return DeployRequest(
        slots=slots,
        group=group,
        port=port,
        clean=clean,
        quiet=quiet,
        dry_run=dry_run,
        yes=yes,
    )


def run_default_interactive(config: str | None = None, state: str | None = None) -> int:
    report = show_project(config=config, state=state)
    print_dashboard(report.config, report.state)

    raw = console.input("  [cyan]Slots or group[/cyan]> ").strip()
    if not raw or raw.lower() in {"q", "quit", "exit"}:
        console.print(f"\n  [yellow]{WARN} cancelled[/yellow]\n")
        return 0

    if raw in report.config.slot_groups:
        request = _deploy_request(group=raw)
    else:
        request = _deploy_request(slots=raw)

    plan = plan_deploy(request, config=config, state=state)
    for warning in plan.warnings:
        console.print(f"  {WARN} {warning}")
    print_deploy_plan(plan.deploy_slots)
    if not confirm(
        "  [yellow]Deploy this plan?[/yellow] [[green]Y[/green]/[red]n[/red]]: ",
        default_yes=True,
    ):
        console.print(f"\n  [yellow]{WARN} aborted[/yellow]\n")
        return 0

    report = deploy_slots(request, config=config, state=state)
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
        typer.Option("--version", "-v", callback=version_callback, is_eager=True, help="Show version."),
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
    force: Annotated[bool, typer.Option("--force", help="Back up and overwrite existing files.")] = False,
) -> None:
    report = init_project(**_ctx_options(ctx, config, state), force=force)

    created = [
        ("config", report.config_created, report.paths.config),
        ("state", report.state_created, report.paths.state),
        ("settings", report.settings_created, report.paths.settings),
        ("gitignore", report.gitignore_created, report.paths.local_gitignore),
    ]
    for name, was_created, path in created:
        if was_created:
            console.print(f"  [green]created {name}:[/green] {path}")
        else:
            console.print(f"  [cyan]{name} exists:[/cyan] {path}")

    if report.legacy_config_exists and not report.config_created:
        console.print(f"  [yellow]{WARN} legacy config exists:[/yellow] {report.paths.root / 'vex_upload_config.yaml'}")
        console.print("  [dim]Run 'fastvex migrate' to create schema v2 config.[/dim]")

    console.print(f"\n  [bold green]{OK} init ok[/bold green]\n")


@app.command("show")
def show_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    report = show_project(**_ctx_options(ctx, config, state))
    print_show(report.config, report.state)


@app.command("status")
def status_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    report = show_project(**_ctx_options(ctx, config, state))
    print_status(report.state)


@app.command("validate")
def validate_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
) -> None:
    report = validate_project(**_ctx_options(ctx, config, state))
    for warning in report.warnings:
        console.print(f"  {WARN} {warning}")
    console.print(f"\n  [bold green]{OK} OK[/bold green]\n")


@app.command("deploy")
def deploy_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
    slots: Annotated[str | None, typer.Option("--slots", help="Slot list, e.g. '1,3,5'.")] = None,
    group: Annotated[str | None, typer.Option("--group", help="Slot group name defined in config.")] = None,
    port: Annotated[str | None, typer.Option("--port", help="Override port. Empty means auto.")] = None,
    clean: Annotated[bool, typer.Option("--clean", help="Run make clean before each actual build.")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help="Capture build/upload output.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Plan without build/upload.")] = False,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirm prompt.")] = False,
) -> None:
    options = _ctx_options(ctx, config, state)
    request = _deploy_request(
        slots=slots,
        group=group,
        port=port,
        clean=clean,
        quiet=quiet,
        dry_run=dry_run,
        yes=yes,
    )
    plan = plan_deploy(request, **options)
    for warning in plan.warnings:
        console.print(f"  {WARN} {warning}")
    print_deploy_plan(plan.deploy_slots)

    if dry_run:
        return

    if not yes:
        if not confirm(
            "  [yellow]Deploy this plan?[/yellow] [[green]Y[/green]/[red]n[/red]]: ",
            default_yes=True,
        ):
            console.print(f"\n  [yellow]{WARN} aborted[/yellow]\n")
            return

    report = deploy_slots(request, **options)
    if report.execution:
        print_execution_result(report.execution)
    _finish(1 if report.failed_slots else 0)


@app.command("migrate")
def migrate_command(
    ctx: typer.Context,
    config: Annotated[str | None, typer.Option("--config", help="v1 config path.")] = None,
    output: Annotated[str | None, typer.Option("--output", help="Output path for generated v2 YAML.")] = None,
    write: Annotated[bool, typer.Option("--write", help="Write fastvex.yaml after backing up v1.")] = False,
) -> None:
    options = _ctx_options(ctx, config, None)
    report = migrate_project(config=options["config"], output=output, write=write)
    for warning in report.warnings:
        console.print(f"  {WARN} {warning}")
    action = "wrote" if report.wrote_in_place else "generated"
    console.print(f"  [green]{OK} {action}:[/green] {report.output}")


@app.command("toolchain")
def toolchain_command(
    rescan: Annotated[bool, typer.Option("--rescan", help="Force re-scan, ignore cache.")] = False,
) -> None:
    report: ToolchainReport = show_toolchain(rescan=rescan)

    if not report.cache.pros_path:
        err_console.print(f"  [yellow]{WARN} PROS not found[/yellow]")
        err_console.print("  [dim]Searched via 'which pros' - run from PROS Terminal first to cache the path.[/dim]")
        _finish(1)
        return

    status = "rescanned" if report.rediscovered else "cached"
    console.print(f"  [green]{OK} PROS found ({status}):[/green]")
    console.print(f"    path: {report.cache.pros_path}")
    if report.cache.discovered_at:
        console.print(f"    cached: {report.cache.discovered_at}")


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
    console.print()
    print_history(report.state.history, limit=limit)


@history_app.command("clean")
def history_clean_command(
    ctx: typer.Context,
    config: CommonConfig = None,
    state: CommonState = None,
    keep: Annotated[int, typer.Option("--keep", help="Number of entries to keep.")] = 10,
) -> None:
    report: HistoryCleanReport = clean_history(**_ctx_options(ctx, config, state), keep=keep)
    if report.removed_count == 0:
        console.print(f"  [dim]history has {report.kept_count} entries, no cleanup needed (keep={keep})[/dim]")
    else:
        console.print(
            f"  [green]{OK} cleaned[/green] {report.removed_count} "
            f"[dim]old entries, kept last[/dim] {report.kept_count}"
        )


def _prog_name() -> str:
    return Path(sys.argv[0]).stem or "fastvex"


def main(argv: list[str] | None = None, prog_name: str | None = None) -> int:
    prog = prog_name or _prog_name()
    try:
        app(args=argv, prog_name=prog, standalone_mode=False)
        return 0
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except click.exceptions.ClickException as exc:
        exc.show(file=err_console.file)
        return int(exc.exit_code)
    except ValidationError as exc:
        err_console.print(f"\n  [bold red]{FAIL} validation error:[/bold red] {exc}\n")
        return 2
    except KeyboardInterrupt:
        err_console.print(f"\n  [yellow]{WARN} interrupted[/yellow]\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
