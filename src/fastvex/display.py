from __future__ import annotations

from collections import OrderedDict

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.padding import Padding

from .models import Config
from .resolve import ResolvedSlot, resolve_slot
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
    if not slots:
        console.print("  [dim]No slots selected.[/dim]\n")
        return

    # Calculate max value length for each build arg key dynamically to ensure perfect vertical alignment
    max_val_lens: dict[str, int] = {}
    for slot in slots:
        for arg in slot.build_args:
            max_val_lens[arg.name] = max(max_val_lens.get(arg.name, 0), len(str(arg.value)))

    console.print()
    table = Table(
        title="[bold cyan]DEPLOYMENT PIPELINE SUMMARY[/bold cyan]",
        title_justify="left",
        box=box.ROUNDED,
        border_style="dim",
        header_style="bold white",
    )
    table.add_column("Slot", justify="center", style="bold white", no_wrap=True)
    table.add_column("Build Profile (Route)", justify="left", no_wrap=True)
    table.add_column("Compiler Flags", justify="left")
    table.add_column("Program Name on Brain", justify="left", no_wrap=True)

    for slot in sorted(slots, key=lambda s: s.slot):
        ps = alliance_style(slot.profile)
        pns = alliance_style(slot.program_name)
        
        formatted_args = []
        for arg in slot.build_args:
            max_len = max_val_lens[arg.name]
            formatted_args.append(f"{arg.name}={arg.value:<{max_len}}")
        args_str = "  ".join(formatted_args)
        
        flags = f"[yellow]{args_str}[/yellow]" if args_str else "[dim]-[/dim]"
        
        table.add_row(
            f"{slot.slot:02d}",
            f"[{ps}]{slot.profile}[/{ps}] [dim]({slot.route})[/dim]",
            flags,
            f"[{pns}]{slot.program_name}[/{pns}]",
        )
        
    console.print(Padding(table, (0, 2)))
    console.print()


def print_execution_result(execution: ExecutionRecord) -> None:
    # 1. Determine title and border style based on execution status
    if execution.status == "success":
        border_style = "green"
        title = f" [bold green]{OK} DEPLOYMENT SUCCESSFUL[/bold green] "
    elif execution.status == "failed":
        border_style = "red"
        title = f" [bold red]{FAIL} DEPLOYMENT FAILED[/bold red] "
    else:
        border_style = "yellow"
        title = f" [bold yellow]DEPLOYMENT {execution.status.upper()}[/bold yellow] "
        
    if execution.dry_run:
        title += "[bold yellow][DRY-RUN][/bold yellow] "

    # 2. Build metadata line
    user_info = f"{execution.username}@{execution.hostname}"
    
    meta_line = Text()
    meta_line.append("Host: ", style="dim")
    meta_line.append(user_info, style="white")
    meta_line.append("   Duration: ", style="dim")
    meta_line.append(f"{execution.duration_sec:.2f}s", style="white")
    meta_line.append("   Builds: ", style="dim")
    meta_line.append(str(len(execution.builds)), style="white")
    meta_line.append("   Uploads: ", style="dim")
    meta_line.append(str(len(execution.uploads)), style="white")

    lines = [meta_line]

    # 3. Build detailed upload summary
    if execution.uploads:
        lines.append(Text(""))
        lines.append(Text("UPLOAD SUMMARY", style="bold white"))
        for upload in execution.uploads:
            pns = alliance_style(upload.program_name)
            slot_str = f"  Slot {upload.slot:02d} {ROCKET} "
            
            line = Text()
            line.append(slot_str, style="dim")
            line.append(f"{upload.program_name:<30}", style=pns)
            
            if upload.status == "success" and upload.step.ok:
                line.append(f"  {OK} SUCCESS", style="bold green")
                line.append(f"  ({upload.step.duration_sec:.2f}s)", style="dim")
            else:
                line.append(f"  {FAIL} FAILED", style="bold red")
                err_detail = upload.reason or upload.step.error or "upload failed"
                line.append(f"  ({err_detail})", style="red dim")
            lines.append(line)

    # 4. Generate the panel
    panel = Panel(
        Text("\n").join(lines),
        title=title,
        title_align="left",
        border_style=border_style,
        padding=(1, 2),
        expand=False,
    )
    
    console.print()
    console.print(Padding(panel, (0, 2)))
    console.print()
