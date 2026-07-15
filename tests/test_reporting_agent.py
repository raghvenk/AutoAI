from pathlib import Path

from qa_agents.models import AutomationRunResult, AutomationRunStatus
from qa_agents.reporting_agent import ReportingAgent
from qa_agents.self_healing_agent import SelfHealingAgent


def test_reporting_agent_writes_execution_report(tmp_path: Path) -> None:
    result = AutomationRunResult(
        project_dir=str(tmp_path),
        target_url="https://staging.example.test",
        command=["python", "-m", "pytest"],
        status=AutomationRunStatus.FAILED,
        exit_code=1,
        duration_seconds=2.4,
        stdout="1 failed, 2 passed in 2.40s",
        stderr="Error: waiting for get_by_text('Submit') timed out",
    )

    report = ReportingAgent().generate(result)

    assert report.summary == "Run failed in 2.4s with 2 passed, 1 failed."
    assert report.total_tests == 3
    assert report.report_json_path
    assert Path(report.report_json_path).is_file()
    assert report.report_markdown_path
    assert Path(report.report_markdown_path).is_file()
    assert report.self_healing


def test_self_healing_agent_suggests_locator_alternatives(tmp_path: Path) -> None:
    result = AutomationRunResult(
        project_dir=str(tmp_path),
        target_url="https://staging.example.test",
        command=["python", "-m", "pytest"],
        status=AutomationRunStatus.FAILED,
        exit_code=1,
        duration_seconds=1.0,
        stderr="TimeoutError: waiting for get_by_label('Email')",
    )

    suggestions = SelfHealingAgent().analyze(result)

    assert suggestions
    assert suggestions[0].failed_locator == "get_by_label('Email')"
    assert "page.get_by_test_id('email')" in suggestions[0].suggested_locators


def test_self_healing_agent_ignores_stopword_locators(tmp_path: Path) -> None:
    result = AutomationRunResult(
        project_dir=str(tmp_path),
        target_url="https://staging.example.test",
        command=["python", "-m", "pytest"],
        status=AutomationRunStatus.FAILED,
        exit_code=1,
        duration_seconds=1.0,
        stderr='TimeoutError: waiting for get_by_label(re.compile(r"to", re.IGNORECASE)).first',
    )

    suggestions = SelfHealingAgent().analyze(result)

    assert suggestions == []
