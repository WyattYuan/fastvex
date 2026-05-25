from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .models import utc_now_iso
from .state_model import StateModel


DEFAULT_TOOLCHAIN_DIR = ".fastvex"
DEFAULT_TOOLCHAIN_FILE = "toolchain.json"


class ToolchainCache(StateModel):
    pros_path: str = ""
    discovered_at: str = ""


def _global_toolchain_path() -> Path:
    return Path.home() / DEFAULT_TOOLCHAIN_DIR / DEFAULT_TOOLCHAIN_FILE


def discover_pros() -> str | None:
    found = shutil.which("pros")
    return str(Path(found)) if found else None


def load_toolchain() -> ToolchainCache:
    path = _global_toolchain_path()
    if not path.is_file():
        return ToolchainCache()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ToolchainCache.model_validate(data)
    except (json.JSONDecodeError, OSError):
        return ToolchainCache()


def save_toolchain(cache: ToolchainCache) -> None:
    path = _global_toolchain_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cache.model_dump(by_alias=True, mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def resolve_toolchain() -> ToolchainCache:
    cache = load_toolchain()
    if cache.pros_path and Path(cache.pros_path).is_file():
        return cache

    discovered = discover_pros()
    if discovered:
        cache = ToolchainCache(pros_path=discovered, discovered_at=utc_now_iso())
        save_toolchain(cache)
    return cache


def get_toolchain_env(cache: ToolchainCache) -> dict[str, str]:
    if not cache.pros_path:
        return {}
    pros_dir = str(Path(cache.pros_path).parent)
    current_path = os.environ.get("PATH", "")
    return {"PATH": pros_dir + os.pathsep + current_path}
