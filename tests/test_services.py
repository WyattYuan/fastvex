from __future__ import annotations

from fastvex.services import DeployRequest, clean_history, clean_project, deploy_slots, get_history, validate_project
from fastvex.state_model import ExecutionRecord, State
from fastvex.storage import load_state, save_state


def test_validate_project_service_returns_warnings(robot_project) -> None:
    report = validate_project(config=str(robot_project / "fastvex.yaml"))

    assert report.warnings == []
    assert report.paths.root == robot_project


def test_deploy_slots_service_returns_structured_report(robot_project, fake_tool_path) -> None:
    report = deploy_slots(
        DeployRequest(slots="3", yes=True, quiet=True),
        config=str(robot_project / "fastvex.yaml"),
    )

    assert report.failed_slots == []
    assert report.execution is not None
    assert report.execution.builds[0].step.command[:4] == ["pros", "make", "MODE=SKILL_COMP", "ROUTE=0"]
    assert "pros upload --slot 3" in fake_tool_path.read_text(encoding="utf-8")


def test_deploy_slots_clears_active_execution_after_success(robot_project, fake_tool_path) -> None:
    deploy_slots(
        DeployRequest(slots="3", yes=True, quiet=True),
        config=str(robot_project / "fastvex.yaml"),
    )

    state = load_state(robot_project / ".fastvex" / "state.json")

    assert state.active_execution is None
    assert state.history[-1].status == "success"


def test_get_history_recovers_running_active_execution(robot_project) -> None:
    state_path = robot_project / ".fastvex" / "state.json"
    save_state(
        state_path,
        State(
            active_execution=ExecutionRecord(
                started_at="2026-05-26T12:00:00+00:00",
                status="running",
                requested_slots=[3],
            )
        ),
    )

    report = get_history(config=str(robot_project / "fastvex.yaml"))
    saved = load_state(state_path)

    assert report.state.active_execution is None
    assert report.state.history[-1].status == "interrupted"
    assert report.state.history[-1].requested_slots == [3]
    assert saved.active_execution is None
    assert saved.history[-1].status == "interrupted"


def test_clean_history_supports_keep_zero(robot_project) -> None:
    state_path = robot_project / ".fastvex" / "state.json"
    save_state(
        state_path,
        State(
            history=[
                ExecutionRecord(started_at="2026-05-26T12:00:00+00:00", status="success"),
                ExecutionRecord(started_at="2026-05-26T12:05:00+00:00", status="success"),
            ]
        ),
    )

    report = clean_history(config=str(robot_project / "fastvex.yaml"), keep=0)
    saved = load_state(state_path)

    assert report.removed_count == 2
    assert report.kept_count == 0
    assert len(report.state.history) == 0
    assert len(saved.history) == 0


def test_clean_history_trims_to_keep_count(robot_project) -> None:
    state_path = robot_project / ".fastvex" / "state.json"
    save_state(
        state_path,
        State(
            history=[
                ExecutionRecord(started_at="2026-05-26T12:00:00+00:00", status="success"),
                ExecutionRecord(started_at="2026-05-26T12:05:00+00:00", status="success"),
                ExecutionRecord(started_at="2026-05-26T12:10:00+00:00", status="success"),
            ]
        ),
    )

    report = clean_history(config=str(robot_project / "fastvex.yaml"), keep=1)
    saved = load_state(state_path)

    assert report.removed_count == 2
    assert report.kept_count == 1
    assert len(report.state.history) == 1
    assert len(saved.history) == 1


def test_clean_project_resets_state(robot_project) -> None:
    state_path = robot_project / ".fastvex" / "state.json"
    save_state(
        state_path,
        State(
            last_port="COM3",
            history=[
                ExecutionRecord(started_at="2026-05-26T12:00:00+00:00", status="success"),
            ],
        ),
    )

    report = clean_project(config=str(robot_project / "fastvex.yaml"))

    assert report.state_reset is True
    assert report.directory_removed is False
    saved = load_state(state_path)
    assert saved.last_port == ""
    assert len(saved.history) == 0
    # .fastvex/ directory should still exist (only state was reset, not removed)
    assert (robot_project / ".fastvex").is_dir()


def test_clean_project_all_removes_directory(robot_project) -> None:
    state_path = robot_project / ".fastvex" / "state.json"
    save_state(state_path, State(last_port="COM3"))
    fastvex_dir = robot_project / ".fastvex"
    assert fastvex_dir.is_dir()

    report = clean_project(config=str(robot_project / "fastvex.yaml"), all=True)

    assert report.directory_removed is True
    assert report.state_reset is False
    assert not fastvex_dir.exists()


def test_clean_project_noop_when_no_state(robot_project) -> None:
    state_path = robot_project / ".fastvex" / "state.json"
    if state_path.exists():
        state_path.unlink()

    report = clean_project(config=str(robot_project / "fastvex.yaml"))

    assert report.state_reset is False
    assert report.directory_removed is False
