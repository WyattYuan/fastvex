from __future__ import annotations

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

import fastvex.cli as cli
from fastvex.cli import main

V1_CONFIG = """schemaVersion: 1
defaults:
  robotName: Sparkle
roles:
  red-comp:
    mode: RED_COMP
    routeSet: red
  blue-debug:
    mode: BLUE_DEBUG
    routeSet: blue
routes:
  red:
    r0:
      route: 0
  blue:
    r1:
      route: 1
activeRoute:
  red: r0
  blue: r1
slots:
  1: { role: red-comp, route: r0 }
  2: { role: blue-debug, route: r1 }
  3: { role: red-comp, route: r0 }
  4: { role: red-comp, route: r0 }
  5: { role: red-comp, route: r0 }
  6: { role: red-comp, route: r0 }
  7: { role: red-comp, route: r0 }
  8: { role: red-comp, route: r0 }
groups:
  all-enabled: [1, 2]
"""


def test_init_creates_config_and_local_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0

    assert (tmp_path / "fastvex.yaml").exists()
    state_path = tmp_path / ".fastvex" / "state.json"
    assert state_path.exists()
    assert (tmp_path / ".fastvex" / "settings.json").exists()
    assert (tmp_path / ".fastvex" / ".gitignore").exists()
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


def test_short_help_flag_matches_help(capsys) -> None:
    assert main(["-h"], prog_name="fvx") == 0
    root_help = capsys.readouterr().out

    assert main(["deploy", "-h"], prog_name="fvx") == 0
    deploy_help = capsys.readouterr().out

    assert "Usage:" in root_help
    assert "fvx" in root_help
    assert "Usage:" in deploy_help
    assert "fvx deploy" in deploy_help


def test_unknown_command_returns_cli_error(capsys) -> None:
    assert main(["nope"], prog_name="fvx") == 2

    captured = capsys.readouterr()
    assert "No such command 'nope'" in captured.err
    assert "Traceback" not in captured.err
    assert "fvx" in captured.err


def test_unknown_option_returns_cli_error(capsys) -> None:
    assert main(["deploy", "--bad"], prog_name="fvx") == 2

    captured = capsys.readouterr()
    assert "No such option '--bad'" in captured.err
    assert "Traceback" not in captured.err


def test_validate_accepts_global_config_before_command(robot_project: Path, monkeypatch) -> None:
    monkeypatch.chdir(robot_project / "src")

    assert main(["--config", str(robot_project / "fastvex.yaml"), "validate"]) == 0


def test_legacy_config_name_requires_migrate(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "vex_upload_config.yaml").write_text("schemaVersion: 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["validate"]) == 2
    captured = capsys.readouterr()
    assert "migrate" in captured.err


def test_migrate_generates_v2_draft_from_legacy_config(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "vex_upload_config.yaml").write_text(V1_CONFIG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["migrate"]) == 0

    output = tmp_path / "fastvex.yaml"
    text = output.read_text(encoding="utf-8")
    assert "schemaVersion: 2" in text
    assert "redComp:" in text
    assert "allEnabled:" in text
    assert "profile: redComp" in text
    captured = capsys.readouterr()
    assert "wrote" in captured.out
    
    backups = list(tmp_path.glob("vex_upload_config.v1.backup.*.yaml"))
    assert len(backups) == 1
    assert not (tmp_path / "vex_upload_config.yaml").exists()


def test_migrate_accepts_global_config_option(tmp_path: Path) -> None:
    source = tmp_path / "old.yaml"
    source.write_text(V1_CONFIG, encoding="utf-8")

    assert main(["--config", str(source), "migrate", "--output", "new.yaml"]) == 0

    assert (tmp_path / "new.yaml").exists()


def test_migrate_write_backs_up_v1_fastvex(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "fastvex.yaml").write_text(V1_CONFIG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["migrate"]) == 0

    assert "schemaVersion: 2" in (tmp_path / "fastvex.yaml").read_text(encoding="utf-8")
    assert list(tmp_path.glob("fastvex.v1.backup.*.yaml"))


def test_old_state_is_backed_up_and_recreated(robot_project: Path, monkeypatch) -> None:
    state_dir = robot_project / ".fastvex"
    state_dir.mkdir()
    (state_dir / "state.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "currentSlots": {
                    "4": {
                        "profileId": "blue-comp:r0",
                        "roleId": "blue-comp",
                        "routeSet": "blue",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(robot_project)

    assert main(["show"]) == 0

    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    assert state["schemaVersion"] == 2
    assert state["currentSlots"] == {}
    assert list(state_dir.glob("state.corrupt.*.json"))


def test_missing_config_returns_validation_error(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["validate"]) == 2
    captured = capsys.readouterr()
    assert "Config file not found" in captured.err
    assert "[bold red]" not in captured.err


def test_dry_run_deploy_does_not_write_history(robot_project: Path, monkeypatch) -> None:
    monkeypatch.chdir(robot_project)

    assert main(["deploy", "--slots", "1,3", "--dry-run"]) == 0

    state_path = robot_project / ".fastvex" / "state.json"
    assert not state_path.exists()


def test_deploy_plan_uses_final_program_name(robot_project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(robot_project)

    assert main(["deploy", "--slots", "3", "--dry-run"]) == 0

    captured = capsys.readouterr()
    assert "skillComp-main-Sparkle" in captured.out


def test_deploy_uses_fake_pros_tools(
    robot_project: Path,
    fake_tool_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(robot_project)

    assert main(["deploy", "--slots", "3", "-y", "--quiet"]) == 0

    log = fake_tool_path.read_text(encoding="utf-8")
    assert "make MODE=SKILL_COMP ROUTE=0" in log
    assert "pros upload --slot 3 --name skillComp-main-Sparkle" in log


def test_default_command_uses_compact_dashboard(
    robot_project: Path,
    fake_tool_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(robot_project)
    monkeypatch.setattr(cli, "console", SimpleNamespace(input=lambda prompt: "q", print=lambda *args, **kwargs: None))

    assert main([]) == 0

    captured = capsys.readouterr()
    assert "fastvex" in captured.out
    assert "Recent History" not in captured.out
    assert "Last Known Slots" not in captured.out


def test_show_displays_slot_plan(robot_project: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(robot_project)

    assert main(["show"]) == 0

    captured = capsys.readouterr()
    assert "Slot Plan" in captured.out
    assert "skillComp-main-Sparkle" in captured.out


def test_make_failure_falls_back_to_pros_make(
    robot_project: Path,
    fake_tool_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(robot_project)
    monkeypatch.setenv("FASTVEX_MAKE_FAIL", "1")

    assert main(["deploy", "--slots", "3", "-y", "--quiet"]) == 0

    log = fake_tool_path.read_text(encoding="utf-8")
    assert "make MODE=SKILL_COMP ROUTE=0" in log
    assert "pros make MODE=SKILL_COMP ROUTE=0" in log
    assert "pros upload --slot 3" in log
