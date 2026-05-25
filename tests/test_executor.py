from __future__ import annotations

from pathlib import Path

import fastvex.executor as executor
from fastvex.executor import CommandResult, CommandRunner, RunOptions, execute_upload
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
        robot_name="Sparkle",
        port="",
        clean=False,
        quiet=True,
        dry_run=dry_run,
        yes=True,
    )


def test_execute_upload_calls_build_then_upload(robot_project: Path) -> None:
    config = load_config(robot_project / "fastvex.yaml")
    state = {}
    runner = FakeRunner()

    execution = execute_upload(robot_project, config, state, _options([3]), runner)

    assert execution["status"] == "success"
    assert runner.calls == [
        ["pros", "make", "MODE=RED_COMP", "ROUTE=0"],
        ["pros", "upload", "--slot", "3", "--name", "RedComp-Sparkle"],
    ]
    assert "3" in state["currentSlots"]


def test_build_failure_does_not_upload(robot_project: Path, monkeypatch) -> None:
    monkeypatch.setattr(executor.os, "cpu_count", lambda: 1)
    config = load_config(robot_project / "fastvex.yaml")
    state = {}
    runner = FakeRunner(
        {
            ("pros", "make", "MODE=RED_COMP", "ROUTE=0"): CommandResult(1, "pros failed"),
            ("make", "MODE=RED_COMP", "ROUTE=0", "-j1"): CommandResult(1, "make failed"),
        }
    )

    execution = execute_upload(robot_project, config, state, _options([3]), runner)

    assert execution["status"] == "failed"
    assert not any(call[:2] == ["pros", "upload"] for call in runner.calls)
    assert state["currentSlots"] == {}


def test_dry_run_does_not_call_runner(robot_project: Path) -> None:
    config = load_config(robot_project / "fastvex.yaml")
    state = {}
    runner = FakeRunner()

    execution = execute_upload(robot_project, config, state, _options([3], dry_run=True), runner)

    assert execution["status"] == "success"
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
    state = {
        "history": [
            {
                "results": [
                    {
                        "profileId": "red-debug:r0",
                        "upload": {"ok": True},
                    }
                ]
            }
        ]
    }

    execute_upload(robot_project, config, state, _options([3]), FakeRunner())

    assert source.stat().st_mtime_ns > before
