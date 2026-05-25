from __future__ import annotations

from typing import Any

from rich.panel import Panel
from rich.text import Text

from .models import resolve_profile, mode_to_camel
from .theme import (
    OK, FAIL, WARN, ROCKET,
    role_tone, console,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _role_style(route_set: str, mode: str) -> str:
    color, is_dim = role_tone(route_set, mode)
    return f"bold {color}" if not is_dim else color


def _styled(text: str, style: str) -> Text:
    """Return a Rich Text with the given style."""
    return Text(text, style=style)


def _render_program_name(config: Any, profile: Any) -> str:
    """Render program name: {modeCamel}{routeKey}-{robotName}"""
    mode_camel = mode_to_camel(profile.mode)
    robot_name = config.defaults.robot_name
    return f"{mode_camel}{profile.route_key}-{robot_name}"


# ─── print_show ──────────────────────────────────────────────────────────────


def print_show(config: Any, state: dict[str, Any]) -> None:
    """Display the full show output: routes, slot mapping, current slots, history."""
    from .theme import role_tone as _rt

    # ── Active routes ──
    route_items = []
    for route_set in sorted(config.active_route.keys()):
        color, _ = _rt(route_set, "COMP")
        key = config.active_route[route_set]
        route_items.append(
            Text(f"{route_set}:{key}", style=f"bold {color}")
        )

    print()
    console.print("  [bold cyan]Active Routes[/bold cyan]")
    for item in route_items:
        console.print(f"  {item}", end="  ")
    console.print()
    print()

    # ── Slot mapping ──
    console.print("  [bold cyan]Slot Mapping[/bold cyan]")
    _print_slot_table(config)
    print()

    # ── Last known current slots ──
    current = state.get("currentSlots", {})
    console.print("  [bold cyan]Last Known Slots[/bold cyan]")
    if not current:
        console.print("  [dim](empty)[/dim]")
    else:
        _print_current_slots(current)
    print()

    # ── Recent history ──
    console.print("  [bold cyan]Recent History[/bold cyan]")
    hist = state.get("history", [])
    if not hist:
        console.print("  [dim](empty)[/dim]")
    else:
        for i, item in enumerate(reversed(hist), 1):
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


def _print_current_slots(current: dict[str, Any]) -> None:
    """Print current slots as formatted lines."""
    for slot in range(1, 9):
        entry = current.get(str(slot))
        if not entry:
            console.print(f"  [dim]Slot {slot}: (unknown)[/dim]")
        else:
            style = _role_style(entry.get("routeSet", ""), entry.get("mode", ""))
            console.print(
                f"  [bold {style}]Slot {slot}[/bold {style}]  "
                f"[{style}]{entry.get('profileId', '')}[/{style}]  "
                f"[green]{ROCKET}[/green]  "
                f"[green]{entry.get('finalName', '')}[/green]"
            )


# ─── History display ─────────────────────────────────────────────────────────


def _print_history_compact(item: dict[str, Any], index: int) -> None:
    """Print one history entry as a compact single line."""
    status   = str(item.get("status"))
    slots    = item.get("requestedSlots", [])
    duration = item.get("durationSec", 0)
    dry      = item.get("dryRun", False)
    user     = item.get("username", "?")
    results  = item.get("results", [])

    # Build line with Text for proper alignment (markup in plain strings causes issues)
    line = Text()

    # Index (indented to match Slot entries)
    line.append(f"  #{index:<2}  ")

    # Status icon + fixed-width text
    if status == "success":
        line.append(OK, style="green")
        line.append(" success   ")  # 8 chars for alignment
    elif status == "failed":
        line.append(FAIL, style="bold red")
        line.append(" failed    ")  # 8 chars for alignment
    else:
        line.append(WARN, style="yellow")
        line.append(f" {status:<8}")

    # Time
    started_raw = item.get("startedAt", "")
    time_str = started_raw[11:19] if len(started_raw) > 19 else ""
    line.append(f"  {time_str:<8}", style="dim")

    # User (fixed width)
    line.append(f"  {user:<15}")

    # Slot list
    slot_list = ",".join(str(s) for s in slots) if slots else "-"
    line.append(f"  {slot_list:<5}", style="bold")

    # Duration
    line.append(f"  {duration}s")

    # Failure details
    for r in results:
        if not r["build"]["ok"]:
            line.append(f"  build={FAIL}", style="bold red")
        if not r["upload"]["ok"]:
            line.append(f"  upload={FAIL}", style="bold red")

    # Dry-run marker at the end
    if dry:
        line.append("  [dry]", style="dim")

    console.print(line)


def print_history(hist: list[dict[str, Any]]) -> None:
    """Print the full history list."""
    if not hist:
        console.print("  [dim](empty)[/dim]")
        return
    for i, item in enumerate(reversed(hist), 1):
        _print_history_compact(item, i)


# ─── Upload plan ─────────────────────────────────────────────────────────────


def print_upload_plan(config: Any, slots: list[int]) -> None:
    """Print the upload plan as a simple list."""
    console.print()
    for slot in slots:
        p = resolve_profile(config, slot)
        prog_name = _render_program_name(config, p)
        route_display = f"[{p.route_key}] {p.route_name}"
        color, _ = role_tone(p.route_set, p.mode)
        console.print(
            f"  [white]Slot {slot}[/white]  "
            f"[{color}]{prog_name}[/{color}]  "
            f"[dim]{route_display}[/dim]"
        )
    console.print()


# ─── Execution result ─────────────────────────────────────────────────────────


def print_execution_result(execution: dict[str, Any]) -> None:
    """Print a summary panel after upload completes."""
    status   = str(execution.get("status", "unknown"))
    results  = execution.get("results", [])
    failed   = [r for r in results if not (r["build"]["ok"] and r["upload"]["ok"])]
    duration = execution.get("durationSec", 0)
    dry      = execution.get("dryRun", False)
    user_info = f"{execution.get('username', '?')}@{execution.get('hostname', '?')}"

    if status == "success":
        status_display = Text(f"{OK} success", style="bold green")
    elif status == "failed":
        status_display = Text(f"{FAIL} failed", style="bold red")
    else:
        status_display = Text(f"{WARN} {status}", style="yellow")

    if dry:
        status_display.append(" [dry-run]", style="dim")

    lines: list[Text] = []
    lines.append(status_display)
    lines.append(Text(f"{ROCKET}  [dim]{user_info}[/dim]"))
    lines.append(Text(f"Duration: {duration}s"))
    lines.append(Text(f"Slots: {len(results)} total"))

    if failed:
        lines.append(Text(""))
        lines.append(Text(f"{FAIL} Failed slots:", style="bold red"))
        for r in failed:
            slot = r.get("slot", "?")
            be   = r.get("build", {}).get("error", "")
            ue   = r.get("upload", {}).get("error", "")
            lines.append(Text(f"  slot {slot}:"))
            if be:
                lines.append(Text(f"    build: {be}", style="red"))
            if ue:
                lines.append(Text(f"    upload: {ue}", style="red"))
    else:
        lines.append(Text(f"{OK} All slots OK", style="green"))

    panel = Panel(
        Text("\n").join(lines),
        border_style="cyan",
        padding=(0, 1),
    )
    console.print(panel)
