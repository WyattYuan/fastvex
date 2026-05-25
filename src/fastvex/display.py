from __future__ import annotations

from typing import Any

from rich.panel import Panel
from rich.text import Text

from .models import mode_to_camel, resolve_profile
from .state_model import ExecutionRecord, State, StateSlotEntry
from .theme import FAIL, OK, ROCKET, WARN, console, role_tone


def _role_style(route_set: str, mode: str) -> str:
    color, is_dim = role_tone(route_set, mode)
    return f"bold {color}" if not is_dim else color


def _render_program_name(config: Any, profile: Any) -> str:
    """Render the same program name used by upload."""
    mode_camel = mode_to_camel(profile.mode)
    robot_name = config.defaults.robot_name
    route_suffix = f"-{profile.route_name}" if profile.route > 0 and profile.route_name else ""
    return config.defaults.name_template.format(
        modeCamel=mode_camel,
        routeSuffix=route_suffix,
        robotName=robot_name,
    )


def print_show(config: Any, state: State) -> None:
    """Display the full show output: routes, slot mapping, current slots, history."""
    from .theme import role_tone as _rt

    route_items = []
    for route_set in sorted(config.active_route.keys()):
        color, _ = _rt(route_set, "COMP")
        key = config.active_route[route_set]
        route_items.append(Text(f"{route_set}:{key}", style=f"bold {color}"))

    print()
    console.print("  [bold cyan]Active Routes[/bold cyan]")
    for item in route_items:
        console.print(f"  {item}", end="  ")
    console.print()
    print()

    console.print("  [bold cyan]Slot Mapping[/bold cyan]")
    _print_slot_table(config)
    print()

    console.print("  [bold cyan]Last Known Slots[/bold cyan]")
    if not state.current_slots:
        console.print("  [dim](empty)[/dim]")
    else:
        _print_current_slots(state.current_slots)
    print()

    console.print("  [bold cyan]Recent History[/bold cyan]")
    if not state.history:
        console.print("  [dim](empty)[/dim]")
    else:
        for i, item in enumerate(reversed(state.history), 1):
            _print_history_compact(item, i)
    print()


def _print_slot_table(config: Any) -> None:
    """Print slot mapping: slot -> program name, route key, route name."""
    for slot in range(1, 9):
        resolved = resolve_profile(config, slot)
        prog_name = _render_program_name(config, resolved)
        route_display = f"[{resolved.route_key}] {resolved.route_name}"
        color, _ = role_tone(resolved.route_set, resolved.mode)

        console.print(
            f"  [white]Slot {slot}[/white]  "
            f"[{color}]{prog_name}[/{color}]  "
            f"[dim]{route_display}[/dim]"
        )


def _print_current_slots(current: dict[int, StateSlotEntry]) -> None:
    """Print current slots as formatted lines."""
    for slot in range(1, 9):
        entry = current.get(slot)
        if not entry:
            console.print(f"  [dim]Slot {slot}: (unknown)[/dim]")
        else:
            style = _role_style(entry.route_set, entry.mode)
            console.print(
                f"  [bold {style}]Slot {slot}[/bold {style}]  "
                f"[{style}]{entry.profile_id}[/{style}]  "
                f"[green]{ROCKET}[/green]  "
                f"[green]{entry.final_name}[/green]"
            )


def _print_history_compact(item: ExecutionRecord, index: int) -> None:
    """Print one history entry as a compact single line."""
    line = Text()
    line.append(f"  #{index:<2}  ")

    if item.status == "success":
        line.append(OK, style="green")
        line.append(" success   ")
    elif item.status == "failed":
        line.append(FAIL, style="bold red")
        line.append(" failed    ")
    else:
        line.append(WARN, style="yellow")
        line.append(f" {item.status:<8}")

    time_str = item.started_at[11:19] if len(item.started_at) > 19 else ""
    line.append(f"  {time_str:<8}", style="dim")
    line.append(f"  {item.username:<15}")

    slot_list = ",".join(str(slot) for slot in item.requested_slots) if item.requested_slots else "-"
    line.append(f"  {slot_list:<5}", style="bold")
    line.append(f"  {item.duration_sec}s")

    for result in item.results:
        if not result.build.ok:
            line.append(f"  build={FAIL}", style="bold red")
        if not result.upload.ok:
            line.append(f"  upload={FAIL}", style="bold red")

    if item.dry_run:
        line.append("  [dry]", style="dim")

    console.print(line)


def print_history(hist: list[ExecutionRecord]) -> None:
    """Print the full history list."""
    if not hist:
        console.print("  [dim](empty)[/dim]")
        return
    for i, item in enumerate(reversed(hist), 1):
        _print_history_compact(item, i)


def print_upload_plan(config: Any, slots: list[int]) -> None:
    """Print the upload plan as a simple list."""
    console.print()
    for slot in slots:
        profile = resolve_profile(config, slot)
        prog_name = _render_program_name(config, profile)
        route_display = f"[{profile.route_key}] {profile.route_name}"
        color, _ = role_tone(profile.route_set, profile.mode)
        console.print(
            f"  [white]Slot {slot}[/white]  "
            f"[{color}]{prog_name}[/{color}]  "
            f"[dim]{route_display}[/dim]"
        )
    console.print()


def print_execution_result(execution: ExecutionRecord) -> None:
    """Print a summary panel after upload completes."""
    failed = [result for result in execution.results if not (result.build.ok and result.upload.ok)]
    user_info = f"{execution.username}@{execution.hostname}"

    if execution.status == "success":
        status_display = Text(f"{OK} success", style="bold green")
    elif execution.status == "failed":
        status_display = Text(f"{FAIL} failed", style="bold red")
    else:
        status_display = Text(f"{WARN} {execution.status}", style="yellow")

    if execution.dry_run:
        status_display.append(" [dry-run]", style="dim")

    lines: list[Text] = [
        status_display,
        Text(f"{ROCKET}  [dim]{user_info}[/dim]"),
        Text(f"Duration: {execution.duration_sec}s"),
        Text(f"Slots: {len(execution.results)} total"),
    ]

    if failed:
        lines.append(Text(""))
        lines.append(Text(f"{FAIL} Failed slots:", style="bold red"))
        for result in failed:
            lines.append(Text(f"  slot {result.slot}:"))
            if result.build.error:
                lines.append(Text(f"    build: {result.build.error}", style="red"))
            if result.upload.error:
                lines.append(Text(f"    upload: {result.upload.error}", style="red"))
    else:
        lines.append(Text(f"{OK} All slots OK", style="green"))

    panel = Panel(
        Text("\n").join(lines),
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)
