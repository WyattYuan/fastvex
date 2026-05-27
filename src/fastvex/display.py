from __future__ import annotations

from collections import OrderedDict

from rich.panel import Panel
from rich.text import Text

from .models import Config
from .resolve import ResolvedSlot, build_arg_strings, resolve_slot
from .state_model import ExecutionRecord, State, StateSlotEntry
from .theme import FAIL, OK, ROCKET, WARN, alliance_style, console




def print_dashboard(config: Config, state: State) -> None:
    """Display the default interactive overview."""
    del state
    console.print()
    name_style = alliance_style(config.robot.name)
    console.print(f"  [bold cyan]fastvex[/bold cyan]  [{name_style}]{config.robot.name}[/{name_style}]")
    console.print()
    print_slot_table(config, compact=True)
    console.print()


def print_show(config: Config, state: State | None = None) -> None:
    """Display the parsed deployment plan."""
    del state
    console.print()
    print_slot_table(config)
    console.print()


def print_status(state: State) -> None:
    console.print()
    console.print("  [bold cyan]Recorded Slot Status[/bold cyan]")
    console.print("  [dim]Recorded status only; not read live from Brain.[/dim]")
    if not state.current_slots:
        console.print("  [dim](empty)[/dim]\n")
        return
    _print_current_slots(state.current_slots)
    console.print()


def print_slot_table(config: Config, *, compact: bool = False) -> None:
    if not compact:
        console.print("  [bold cyan]Slot Plan[/bold cyan]")
    for slot in range(1, 9):
        resolved = resolve_slot(config, slot)
        if resolved is None:
            console.print(f"  [white]{slot}[/white]  [dim]empty[/dim]")
            continue
        if compact:
            ps = alliance_style(resolved.profile)
            pns = alliance_style(resolved.program_name)
            console.print(
                f"  [white]{slot}[/white]  "
                f"[{ps}]{resolved.profile:<10}[/{ps}] "
                f"[dim]{resolved.route:<8}[/dim] "
                f"[{pns}]{resolved.program_name}[/{pns}]"
            )
        else:
            ps = alliance_style(resolved.profile)
            als = alliance_style(resolved.alliance)
            pns = alliance_style(resolved.program_name)
            console.print(
                f"  [white]Slot {slot}[/white]  "
                f"[{ps}]{resolved.profile:<10}[/{ps}] "
                f"[{als}]{resolved.alliance:<5}[/{als}] "
                f"[dim]{resolved.route:<8}[/dim] "
                f"[{pns}]{resolved.program_name}[/{pns}]"
            )


def _print_current_slots(current: dict[int, StateSlotEntry]) -> None:
    for slot in range(1, 9):
        entry = current.get(slot)
        if not entry:
            console.print(f"  [dim]Slot {slot}: (unknown)[/dim]")
        else:
            ps = alliance_style(entry.profile)
            pns = alliance_style(entry.program_name)
            console.print(
                f"  [white]Slot {slot}[/white]  "
                f"[{ps}]{entry.profile:<10}[/{ps}] "
                f"[dim]{entry.route:<8}[/dim] "
                f"[{pns}]{ROCKET} {entry.program_name}[/{pns}]"
            )


def _print_history_compact(item: ExecutionRecord, index: int) -> None:
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
    slot_list = ",".join(str(slot) for slot in item.requested_slots) if item.requested_slots else "-"
    line.append(f"  {slot_list:<8}", style="bold")
    line.append(f"  builds={len(item.builds)} uploads={len(item.uploads)}")
    if item.dry_run:
        line.append("  [dry]", style="dim")
    console.print(line)


def print_history(hist: list[ExecutionRecord], *, limit: int | None = None) -> None:
    if not hist:
        console.print("  [dim](empty)[/dim]")
        return
    shown = list(reversed(hist))[:limit]
    for i, item in enumerate(shown, 1):
        _print_history_compact(item, i)
    if limit is not None and len(hist) > limit:
        console.print(f"  [dim]showing last {limit} of {len(hist)}[/dim]")


def _group_by_build(slots: list[ResolvedSlot]) -> OrderedDict[str, list[ResolvedSlot]]:
    grouped: OrderedDict[str, list[ResolvedSlot]] = OrderedDict()
    for slot in slots:
        grouped.setdefault(slot.build_key + repr([(arg.name, arg.value) for arg in slot.build_args]), []).append(slot)
    return grouped


def print_deploy_plan(slots: list[ResolvedSlot]) -> None:
    console.print()
    for grouped_slots in _group_by_build(slots).values():
        first = grouped_slots[0]
        ps = alliance_style(first.profile)
        console.print(f"  [bold cyan]Build[/bold cyan] [{ps}]{first.profile}[/{ps}]:{first.route}")
        args = " ".join(build_arg_strings(first.build_args)) or "(none)"
        console.print(f"    [dim]args:[/dim] {args}")
        console.print("    [dim]upload:[/dim]")
        for slot in grouped_slots:
            pns = alliance_style(slot.program_name)
            console.print(f"      slot {slot.slot} -> [{pns}]{slot.program_name}[/{pns}]")
    console.print()


def print_execution_result(execution: ExecutionRecord) -> None:
    failed = [upload for upload in execution.uploads if upload.status != "success" or not upload.step.ok]
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
        Text(f"{ROCKET}  {user_info}", style="dim"),
        Text(f"Duration: {execution.duration_sec}s"),
        Text(f"Builds: {len(execution.builds)}"),
        Text(f"Uploads: {len(execution.uploads)}"),
    ]

    if failed:
        lines.append(Text(""))
        lines.append(Text(f"{FAIL} Failed uploads:", style="bold red"))
        for upload in failed:
            detail = upload.reason or upload.step.error or "upload failed"
            lines.append(Text(f"  slot {upload.slot}: {detail}", style="red"))
    else:
        lines.append(Text(f"{OK} All uploads OK", style="green"))

    panel = Panel(
        Text("\n").join(lines),
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)
