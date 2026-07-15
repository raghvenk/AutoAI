from pathlib import Path

from fastapi.testclient import TestClient

from qa_agents import web
from qa_agents.models import AutomationRunResult, AutomationRunStatus
from qa_agents.models import TestCaseSuite as Suite

SUITE = Suite.model_validate(
    {
        "feature": "Profile",
        "source_summary": "Profile editing requirements.",
        "test_cases": [
            {
                "id": "TC-001",
                "title": "Update display name",
                "objective": "Verify a user can update their name.",
                "test_type": "functional",
                "priority": "high",
                "steps": [
                    {
                        "step": 1,
                        "action": "Save a new display name",
                        "expected_result": "The new display name appears",
                    }
                ],
                "expected_result": "The profile is updated.",
            }
        ],
    }
)


def test_home_page() -> None:
    response = TestClient(web.app).get("/")

    assert response.status_code == 200
    assert "Generate test cases" in response.text


def test_generate_and_download(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web, "OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(web.TestCaseAgent, "generate", lambda self, sources, instructions: SUITE)
    client = TestClient(web.app)

    response = client.post("/api/generate", data={"requirements": "A user can update their name."})

    assert response.status_code == 200
    payload = response.json()
    assert payload["suite"]["feature"] == "Profile"
    download = client.get(payload["downloads"]["csv"])
    assert download.status_code == 200
    assert "TC-001" in download.text


def test_rejects_empty_request() -> None:
    response = TestClient(web.app).post("/api/generate")

    assert response.status_code == 400


def test_runs_generated_automation_project(monkeypatch, tmp_path: Path) -> None:
    result_id = "a" * 32
    project = tmp_path / result_id / "project"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_generated.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(web, "AUTOMATION_OUTPUT_ROOT", tmp_path)

    def fake_run(self, project_dir, target_url, headed=False):
        return AutomationRunResult(
            project_dir=str(project_dir),
            target_url=target_url,
            command=["python", "-m", "pytest"],
            status=AutomationRunStatus.PASSED,
            exit_code=0,
            duration_seconds=0.1,
            stdout="1 passed",
        )

    monkeypatch.setattr(web.AutomationRunnerAgent, "run", fake_run)

    response = TestClient(web.app).post(
        f"/api/run-automation/{result_id}",
        data={"target_url": "https://staging.example.test"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "passed"


def test_runner_endpoint_runs_workspace_project(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "generated-project"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_generated.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(web, "PROJECT_ROOT", tmp_path)

    def fake_run(self, project_dir, target_url, headed=False, timeout_seconds=600, pytest_args=None):
        return AutomationRunResult(
            project_dir=str(project_dir),
            target_url=target_url,
            command=["python", "-m", "pytest", *(pytest_args or [])],
            status=AutomationRunStatus.PASSED,
            exit_code=0,
            duration_seconds=0.1,
            stdout="1 passed",
        )

    monkeypatch.setattr(web.AutomationRunnerAgent, "run", fake_run)

    response = TestClient(web.app).post(
        "/api/runner/run",
        data={
            "project_dir": "generated-project",
            "target_url": "https://staging.example.test",
            "pytest_args": "-k smoke",
            "timeout_seconds": "60",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["result"]["status"] == "passed"
    assert payload["result"]["command"][-2:] == ["-k", "smoke"]


def test_runner_endpoint_rejects_project_outside_workspace(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(web, "PROJECT_ROOT", workspace)

    response = TestClient(web.app).post(
        "/api/runner/run",
        data={"project_dir": str(outside), "target_url": "https://staging.example.test"},
    )

    assert response.status_code == 422


def test_downloads_runner_report_as_markdown_json_and_csv(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    report_dir = workspace / "output" / "automation-web" / ("a" * 32) / "project" / "test-results"
    report_dir.mkdir(parents=True)
    markdown = report_dir / "autoai-execution-report-20260702-000000.md"
    json_report = report_dir / "autoai-execution-report-20260702-000000.json"
    markdown.write_text("# Report\n", encoding="utf-8")
    json_report.write_text(
        """
        {
          "status": "failed",
          "target_url": "https://staging.example.test",
          "project_dir": "project",
          "exit_code": 1,
          "duration_seconds": 1.2,
          "total_tests": 1,
          "passed_tests": 0,
          "failed_tests": 1,
          "summary": "Run failed.",
          "findings": ["One failure"],
          "self_healing": []
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(web, "PROJECT_ROOT", workspace)
    client = TestClient(web.app)

    md_response = client.get("/api/report-download", params={"path": str(markdown), "file_type": "md"})
    json_response = client.get("/api/report-download", params={"path": str(markdown), "file_type": "json"})
    csv_response = client.get("/api/report-download", params={"path": str(markdown), "file_type": "csv"})

    assert md_response.status_code == 200
    assert json_response.status_code == 200
    assert csv_response.status_code == 200
    assert "Run failed." in csv_response.text
