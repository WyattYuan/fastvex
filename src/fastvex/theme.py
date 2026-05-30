from __future__ import annotations

from datetime import datetime, timedelta, timezone

import click
from rich.console import Console

_console: Console | None = None
_err_console: Console | None = None


def _get_console() -> Console:
    global _console
    if _console is None:
        _console = Console()
    return _console


def _get_err_console() -> Console:
    global _err_console
    if _err_console is None:
        _err_console = Console(stderr=True)
    return _err_console


class _ConsoleProxy:
    """Lazy proxy that defers Console() creation until first attribute access."""

    __slots__ = ("_target",)

    def __init__(self, target: str) -> None:
        self._target = target

    def __getattr__(self, name: str):
        getter = _get_console if self._target == "out" else _get_err_console
        return getattr(getter(), name)


console = _ConsoleProxy("out")  # type: ignore[assignment]
err_console = _ConsoleProxy("err")  # type: ignore[assignment]

# ─── Status symbols ─────────────────────────────────────────────────────────

OK   = "[+]"
FAIL = "[x]"
WARN = "[!]"
INFO = "[*]"
ROCKET = "->"

# ─── Color/style constants ────────────────────────────────────────────────────


def alliance_style(text: str) -> str:
    """Return a Rich style string for an alliance/profile/program-name string.

    Single source of truth for the red/blue/skill → color mapping used
    throughout the display layer.  Debug profiles are rendered in bold
    so that e.g. ``redComp`` and ``redDebug`` are visually distinct
    without changing the base colour.
    """
    lower = text.lower()
    if "red" in lower:
        base = "#ff5c5c"
    elif "blue" in lower:
        base = "#60a5fa"
    elif "skill" in lower:
        base = "#fbbf24"
    else:
        base = "#38bdf8"
    if "debug" in lower:
        return f"{base} bold"
    return base


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
