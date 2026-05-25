from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.text import Text

console = Console()

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


def _color_name_to_rich(name: str) -> str:
    """Map our color names to rich color names."""
    return name


# ─── Text helpers ────────────────────────────────────────────────────────────


def c(text: str, color: str) -> Text:
    """Colorize text using Rich ANSI codes.

    color can be: RESET, BOLD, DIM, CYAN, GREEN, YELLOW, RED, BLUE,
    MAGENTA, BRIGHT_RED, BRIGHT_GREEN, BRIGHT_YELLOW, BRIGHT_BLUE, BRIGHT_CYAN
    or a rich color name string.
    """
    from rich.style import Style
    style = Style.parse(color)
    return Text(text, style=style)


def cbold(text: str, color: str) -> Text:
    from rich.style import Style
    return Text(text, style=Style.parse(f"bold {color}"))


def status_text(text: str, color: str) -> Text:
    """Create a Rich Text with color for status display."""
    return Text(text, style=color)


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
    answer = console.input(prompt).strip().lower()
    if not answer:
        return default_yes
    return answer in {"y", "yes"}
