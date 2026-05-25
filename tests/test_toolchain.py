from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from fastvex.cli import main
from fastvex.services import show_toolchain
from fastvex.toolchain import (
    ToolchainCache,
    discover_pros,
    get_toolchain_env,
    load_toolchain,
    resolve_toolchain,
    save_toolchain,
)


@pytest.fixture(autouse=True)
def _isolate_global_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect ~/.fastvex to a temp dir so tests don't touch real home."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr("fastvex.toolchain.Path.home", lambda: fake_home)
    return fake_home


def test_discover_pros_finds_from_path(fake_tool_path: Path):
    found = discover_pros()
    assert found is not None
    assert Path(found).name.startswith("pros")


def test_discover_pros_returns_none_when_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PATH", "")
    found = discover_pros()
    assert found is None


def test_save_and_load_toolchain():
    cache = ToolchainCache(pros_path="/usr/bin/pros", discovered_at="2026-01-01T00:00:00+08:00")
    save_toolchain(cache)

    loaded = load_toolchain()
    assert loaded.pros_path == "/usr/bin/pros"
    assert loaded.discovered_at == "2026-01-01T00:00:00+08:00"


def test_load_toolchain_returns_empty_when_missing():
    loaded = load_toolchain()
    assert loaded.pros_path == ""
    assert loaded.discovered_at == ""


def test_resolve_toolchain_caches_result(fake_tool_path: Path):
    cache = resolve_toolchain()
    assert cache.pros_path != ""
    assert cache.discovered_at != ""

    loaded = load_toolchain()
    assert loaded.pros_path == cache.pros_path


def test_resolve_toolchain_uses_cache_when_valid(fake_tool_path: Path):
    first = resolve_toolchain()
    second = resolve_toolchain()
    assert second.pros_path == first.pros_path
    assert second.discovered_at == first.discovered_at


def test_resolve_toolchain_rediscoveres_when_stale(fake_tool_path: Path, tmp_path: Path):
    # Pre-populate cache with a nonexistent path
    stale = ToolchainCache(pros_path="/nonexistent/pros", discovered_at="2020-01-01T00:00:00+08:00")
    save_toolchain(stale)

    fresh = resolve_toolchain()
    assert fresh.pros_path != "/nonexistent/pros"
    assert fresh.pros_path != ""


def test_get_toolchain_env_prepends_path():
    pros_path = str(Path("/opt/pros-cli/pros.exe"))
    cache = ToolchainCache(pros_path=pros_path)
    env = get_toolchain_env(cache)
    assert "PATH" in env
    pros_dir = str(Path(pros_path).parent)
    assert env["PATH"].startswith(pros_dir)


def test_get_toolchain_env_returns_empty_for_missing():
    cache = ToolchainCache()
    env = get_toolchain_env(cache)
    assert env == {}


def test_toolchain_cli_command(fake_tool_path: Path):
    code = main(["toolchain"])
    assert code == 0


def test_toolchain_cli_not_found(monkeypatch: pytest.MonkeyPatch):
    from fastvex.toolchain import _global_toolchain_path

    # Clean cache before clearing PATH
    cache_path = _global_toolchain_path()
    if cache_path.is_file():
        cache_path.unlink()

    monkeypatch.setenv("PATH", "")
    report = show_toolchain()
    assert report.cache.pros_path == ""


def test_toolchain_rescan(fake_tool_path: Path):
    # First run to populate cache
    main(["toolchain"])
    # Rescan should still succeed
    code = main(["toolchain", "--rescan"])
    assert code == 0
