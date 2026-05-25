from __future__ import annotations

import json
from pathlib import Path

from fastvex.cli import main
from fastvex.templates import DEFAULT_CONFIG_TEXT


def test_init_creates_config_and_local_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0

    assert (tmp_path / "fastvex.yaml").exists()
    state_path = tmp_path / ".fastvex" / "state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["currentSlots"] == {}


def test_validate_finds_config_from_child_directory(robot_project: Path, monkeypatch) -> None:
    child = robot_project / "src"
    monkeypatch.chdir(child)

    assert main(["validate"]) == 0


def test_legacy_config_name_is_readable(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "vex_upload_config.yaml").write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["validate"]) == 0
    captured = capsys.readouterr()
    assert "legacy config name" in captured.out


def test_missing_config_returns_validation_error(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["validate"]) == 2
    captured = capsys.readouterr()
    assert "Config file not found" in captured.err


def test_dry_run_upload_writes_default_local_state(robot_project: Path, monkeypatch) -> None:
    monkeypatch.chdir(robot_project)

    assert main(["upload", "--slots", "1,3", "--dry-run"]) == 0

    state_path = robot_project / ".fastvex" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["history"][-1]["dryRun"] is True
    assert state["history"][-1]["requestedSlots"] == [1, 3]


def test_upload_uses_fake_pros_tools(
    robot_project: Path,
    fake_tool_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(robot_project)

    assert main(["upload", "--slots", "3", "-y", "--quiet"]) == 0

    log = fake_tool_path.read_text(encoding="utf-8")
    assert "pros make MODE=RED_COMP ROUTE=0" in log
    assert "pros upload --slot 3 --name RedComp-Evergarden" not in log
    assert "pros upload --slot 3 --name RedComp-Sparkle" in log


def test_pros_make_failure_falls_back_to_make(
    robot_project: Path,
    fake_tool_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(robot_project)
    monkeypatch.setenv("FASTVEX_PROS_MAKE_FAIL", "1")

    assert main(["upload", "--slots", "3", "-y", "--quiet"]) == 0

    log = fake_tool_path.read_text(encoding="utf-8")
    assert "pros make MODE=RED_COMP ROUTE=0" in log
    assert "make MODE=RED_COMP ROUTE=0" in log
    assert "pros upload --slot 3" in log
