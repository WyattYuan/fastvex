from __future__ import annotations

import os
import shutil
from pathlib import Path

_resolved_cache: str | None = None


def discover_pros() -> str | None:
    found = shutil.which("pros")
    return str(Path(found)) if found else None


def invalidate_toolchain_cache() -> None:
    global _resolved_cache
    _resolved_cache = None


def resolve_toolchain() -> str | None:
    global _resolved_cache
    if _resolved_cache is not None:
        return _resolved_cache
    _resolved_cache = discover_pros()
    return _resolved_cache


def get_toolchain_env(pros_path: str | None) -> dict[str, str]:
    if not pros_path:
        return {}
    pros_dir = str(Path(pros_path).parent)
    current_path = os.environ.get("PATH", "")
    return {"PATH": pros_dir + os.pathsep + current_path}
