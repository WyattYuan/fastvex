from __future__ import annotations

from pathlib import Path

import fastvex.executor as executor
from fastvex.executor import CommandResult, CommandRunner, RunOptions, execute_deploy
from fastvex.state_model import BuildSignature
from fastvex.state_model import State
from fastvex.storage import load_config


class FakeRunner(CommandRunner):
    def __init__(self, failures: dict[tuple[str, ...], CommandResult] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.failures = failures or {}

    def run(self, args: list[str], cwd: Path, quiet: bool) -> CommandResult:
        del cwd, quiet
        self.calls.append(args)
        return self.failures.get(tuple(args), CommandResult(0, ""))


def _options(slots: list[int], *, dry_run: bool = False) -> RunOptions:
    return RunOptions(
        slots=slots,
        port="",
        clean=False,
        quiet=True,
        dry_run=dry_run,
        yes=True,
    )


def test_execute_deploy_calls_build_then_upload(robot_project: Path) -> None:
    config = load_config(robot_project / "fastvex.yaml")
    state = State()
    runner = FakeRunner()

    execution = execute_deploy(robot_project, config, state, _options([3]), runner)

    assert execution.status == "success"
    assert execution.builds[0].step.command == ["pros", "make", "MODE=SKILL_COMP", "ROUTE=0"]
    assert execution.builds[0].step.returncode == 0
    assert execution.uploads[0].step.command == [
        "pros",
        "upload",
        "--slot",
        "3",
        "--name",
        "skillComp-main-Sparkle",
    ]
    assert runner.calls == [
        ["pros", "make", "MODE=SKILL_COMP", "ROUTE=0"],
        ["pros", "upload", "--slot", "3", "--name", "skillComp-main-Sparkle"],
    ]
    assert 3 in state.current_slots


def test_execute_deploy_checkpoints_confirmed_progress(robot_project: Path) -> None:
    config = load_config(robot_project / "fastvex.yaml")
    state = State()
    runner = FakeRunner()
    checkpoints = []

    execute_deploy(
        robot_project,
        config,
        state,
        _options([3]),
        runner,
        checkpoint=lambda execution: checkpoints.append(execution.model_copy(deep=True)),
    )

    assert checkpoints[0].status == "running"
    assert checkpoints[0].builds == []
    assert checkpoints[1].builds[0].step.ok is True
    assert checkpoints[1].uploads == []
    assert checkpoints[-1].status == "success"
    assert checkpoints[-1].uploads[0].status == "success"


def test_build_failure_does_not_upload(robot_project: Path, monkeypatch) -> None:
    monkeypatch.setattr(executor.os, "cpu_count", lambda: 1)
    config = load_config(robot_project / "fastvex.yaml")
    state = State()
    runner = FakeRunner(
        {
            ("pros", "make", "MODE=SKILL_COMP", "ROUTE=0"): CommandResult(1, "pros failed"),
            ("make", "MODE=SKILL_COMP", "ROUTE=0", "-j1"): CommandResult(1, "make failed"),
        }
    )

    execution = execute_deploy(robot_project, config, state, _options([3]), runner)

    assert execution.status == "failed"
    assert not any(call[:2] == ["pros", "upload"] for call in runner.calls)
    assert state.current_slots == {}


def test_dry_run_does_not_call_runner(robot_project: Path) -> None:
    config = load_config(robot_project / "fastvex.yaml")
    state = State()
    runner = FakeRunner()

    execution = execute_deploy(robot_project, config, state, _options([3], dry_run=True), runner)

    assert execution.status == "success"
    assert runner.calls == []


def test_profile_switch_touches_compile_time_dependent_sources(robot_project: Path) -> None:
    config = load_config(robot_project / "fastvex.yaml")
    source = robot_project / "src" / "main.cpp"
    old_time = 1_700_000_000
    source.touch()
    source_stat_path = str(source)
    import os

    os.utime(source_stat_path, (old_time, old_time))
    before = source.stat().st_mtime_ns
    state = State()
    state.last_build_signature = BuildSignature(profile="redDebug", route="left", build_args=[])

    execute_deploy(robot_project, config, state, _options([3]), FakeRunner())

    assert source.stat().st_mtime_ns > before


def test_profile_switch_tracks_successful_build_even_when_upload_fails(
    robot_project: Path,
    monkeypatch,
) -> None:
    config = load_config(robot_project / "fastvex.yaml")
    state = State()

    class TouchProbe:
        def __init__(self) -> None:
            self.count = 0

        def touch(self) -> None:
            self.count += 1

    probe = TouchProbe()
    monkeypatch.setattr(
        executor,
        "find_compile_time_dependent_sources",
        lambda project_root: [probe],
    )

    runner = FakeRunner(
        {
            ("pros", "upload", "--slot", "4", "--name", "redDebug-left-Sparkle"): CommandResult(
                1,
                "upload failed",
            )
        }
    )

    execute_deploy(robot_project, config, state, _options([4, 3]), runner)

    assert probe.count == 2


def test_state_model_reads_json_slot_keys_as_ints() -> None:
    state = State.model_validate(
        {
            "currentSlots": {
                "3": {
                    "profile": "skillComp",
                    "alliance": "skill",
                    "route": "main",
                    "programName": "skillComp-main-Sparkle",
                    "uploadedAt": "2026-05-25T17:00:00+08:00",
                }
            }
        }
    )

    assert 3 in state.current_slots
