from __future__ import annotations

import json
import tomllib
from pathlib import Path

import fastvex.cli as cli
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


def test_fvx_console_script_alias_is_published() -> None:
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"]["fastvex"] == "fastvex.cli:main"
    assert metadata["project"]["scripts"]["fvx"] == "fastvex.cli:main"


def test_help_uses_invoked_program_name(capsys) -> None:
    assert main(["--help"], prog_name="fvx") == 0

    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "fvx" in captured.out


def test_validate_accepts_global_config_before_command(robot_project: Path, monkeypatch) -> None:
    monkeypatch.chdir(robot_project / "src")

    assert main(["--config", str(robot_project / "fastvex.yaml"), "validate"]) == 0


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
    assert "[bold red]" not in captured.err


def test_dry_run_upload_writes_default_local_state(robot_project: Path, monkeypatch) -> None:
    monkeypatch.chdir(robot_project)

    assert main(["upload", "--slots", "1,3", "--dry-run"]) == 0

    state_path = robot_project / ".fastvex" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["history"][-1]["dryRun"] is True
    assert state["history"][-1]["requestedSlots"] == [1, 3]
    assert state["history"][-1]["results"][0]["build"]["command"] == []


def test_upload_plan_uses_final_program_name(robot_project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(robot_project)

    assert main(["upload", "--slots", "3", "--dry-run"]) == 0

    captured = capsys.readouterr()
    assert "RedComp-Sparkle" in captured.out
    assert "RedCompr0-Sparkle" not in captured.out


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


def test_default_command_uses_compact_dashboard(robot_project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(robot_project)
    monkeypatch.setattr(cli.console, "input", lambda prompt: "q")

    assert main([]) == 0

    captured = capsys.readouterr()
    assert "Target" in captured.out
    assert "Recent History" not in captured.out
    assert "Last Known Slots" not in captured.out


def test_show_limits_recent_history_by_default(robot_project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(robot_project)
    for _ in range(4):
        assert main(["upload", "--slots", "3", "--dry-run"]) == 0

    assert main(["show"]) == 0

    captured = capsys.readouterr()
    assert "showing last 3 of 4" in captured.out

    assert main(["show", "--full"]) == 0
    captured = capsys.readouterr()
    assert "showing last 3 of 4" not in captured.out


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
