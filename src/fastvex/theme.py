from __future__ import annotations

from datetime import datetime, timedelta, timezone

import click
from rich.console import Console

console = Console()
err_console = Console(stderr=True)

# ─── Status symbols ─────────────────────────────────────────────────────────

OK   = "[+]"
FAIL = "[x]"
WARN = "[!]"
INFO = "[*]"
ROCKET = "->"

# ─── Color/style constants ────────────────────────────────────────────────────


def role_tone(route_set: str, mode: str) -> tuple[str, bool]:
    """Return (color_name, is_dim). Rich uses named colors."""
    rs = route_set.lower()
    is_debug = "DEBUG" in mode.upper()

    if rs == "red":
        return ("red",    False) if not is_debug else ("magenta",  False)
    if rs == "blue":
        return ("blue",   False) if not is_debug else ("cyan",     False)
    if rs == "skill":
        return ("yellow", False) if not is_debug else ("green",    False)
    return ("cyan", False)


# ─── Timestamp ───────────────────────────────────────────────────────────────


def format_bj_timestamp(value: str | None) -> str:
    """Format an ISO timestamp as 'YYYY-MM-DD HH:MM:SS UTC+8'."""
    if not value:
        return "(unknown)"
    raw = value.strip()
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        bj = dt.astimezone(timezone(timedelta(hours=8)))
        return bj.strftime("%Y-%m-%d %H:%M:%S UTC+8")
    except ValueError:
        return raw


# ─── Confirm ─────────────────────────────────────────────────────────────────


def confirm(prompt: str, *, default_yes: bool = False) -> bool:
    """Ask user for yes/no confirmation.

    If user presses Enter without input, returns default_yes.
    """
    console.print(prompt, end="")
    try:
        answer = click.getchar().lower()
    except (KeyboardInterrupt, EOFError):
        raise
    except Exception:
        answer = console.input("").strip().lower()

    if answer in {"\r", "\n", ""}:
        console.print()
        return default_yes
    if answer == "y":
        console.print("y")
        return True
    if answer == "n":
        console.print("n")
        return False
    console.print(answer)
    return False
