from __future__ import annotations

from pathlib import Path

import pytest

from fastvex.cli import main
from fastvex.services import show_toolchain
from fastvex.toolchain import (
    discover_pros,
    get_toolchain_env,
    invalidate_toolchain_cache,
    resolve_toolchain,
)


def test_discover_pros_finds_from_path(fake_tool_path: Path):
    found = discover_pros()
    assert found is not None
    assert Path(found).name.startswith("pros")


def test_discover_pros_returns_none_when_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PATH", "")
    found = discover_pros()
    assert found is None


def test_resolve_toolchain_caches_in_process(fake_tool_path: Path):
    invalidate_toolchain_cache()
    first = resolve_toolchain()
    assert first is not None

    second = resolve_toolchain()
    assert second == first


def test_resolve_toolchain_returns_none_when_missing(monkeypatch: pytest.MonkeyPatch):
    invalidate_toolchain_cache()
    monkeypatch.setenv("PATH", "")
    result = resolve_toolchain()
    assert result is None


def test_invalidate_clears_cache(fake_tool_path: Path):
    invalidate_toolchain_cache()
    first = resolve_toolchain()
    assert first is not None

    invalidate_toolchain_cache()
    second = resolve_toolchain()
    assert second == first  # same result, but was re-discovered


def test_get_toolchain_env_prepends_path():
    pros_path = str(Path("/opt/pros-cli/pros.exe"))
    env = get_toolchain_env(pros_path)
    assert "PATH" in env
    pros_dir = str(Path(pros_path).parent)
    assert env["PATH"].startswith(pros_dir)


def test_get_toolchain_env_returns_empty_for_none():
    env = get_toolchain_env(None)
    assert env == {}


def test_get_toolchain_env_returns_empty_for_empty():
    env = get_toolchain_env("")
    assert env == {}


def test_toolchain_cli_command(fake_tool_path: Path):
    code = main(["toolchain"])
    assert code == 0


def test_toolchain_cli_not_found(monkeypatch: pytest.MonkeyPatch):
    invalidate_toolchain_cache()
    monkeypatch.setenv("PATH", "")
    report = show_toolchain()
    assert report.pros_path == ""


def test_toolchain_rescan(fake_tool_path: Path):
    main(["toolchain"])
    code = main(["toolchain", "--rescan"])
    assert code == 0
