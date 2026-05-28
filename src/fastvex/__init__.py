from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path


def _read_version_from_pyproject() -> str | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            match = re.search(r'^version\s*=\s*"([^"]+)"', candidate.read_text(), re.M)
            return match.group(1) if match else None
    return None


try:
    __version__ = importlib.metadata.version("fastvex")
except importlib.metadata.PackageNotFoundError:
    __version__ = _read_version_from_pyproject() or "0.0.0.dev"

__all__ = ["__version__"]
