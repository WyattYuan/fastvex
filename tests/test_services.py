from __future__ import annotations

from fastvex.services import DeployRequest, deploy_slots, validate_project


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
    assert report.execution.builds[0].step.command == ["pros", "make", "MODE=SKILL_COMP", "ROUTE=0"]
    assert "pros upload --slot 3" in fake_tool_path.read_text(encoding="utf-8")
