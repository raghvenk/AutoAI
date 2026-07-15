from pathlib import Path

import pytest

from qa_agents.automation_runner_agent import AutomationRunnerAgent


def test_runs_generated_pytest_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    tests_dir = project / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_generated.py").write_text(
        "def test_target_url_is_available():\n"
        "    import os\n"
        "    assert os.environ['TEST_URL'] == 'https://staging.example.test'\n",
        encoding="utf-8",
    )

    result = AutomationRunnerAgent().run(project, "https://staging.example.test", timeout_seconds=30)

    assert result.status.value == "passed"
    assert result.exit_code == 0
    assert result.report_json_path
    assert Path(result.report_json_path).is_file()
    assert result.report_markdown_path
    assert Path(result.report_markdown_path).is_file()


def test_rejects_non_automation_project(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing tests"):
        AutomationRunnerAgent().run(tmp_path, "https://staging.example.test")
