from pathlib import Path

from qa_agents.dom_agent import DomInspectionAgent
from qa_agents.models import DomInspectionReport, DomPage
from qa_agents.test_management_agent import TestManagementExportAgent


def test_exports_page_object_model(tmp_path: Path) -> None:
    report = DomInspectionReport(
        target_url="https://staging.example.test",
        pages=[
            DomPage.model_validate(
                {
                    "url": "https://staging.example.test",
                    "title": "Login",
                    "elements": [
                        {
                            "tag": "button",
                            "role": "button",
                            "text": "Sign in",
                            "selector_candidates": [
                                {
                                    "selector": "page.get_by_role('button', name='Sign in')",
                                    "strategy": "role-name",
                                    "stability": "high",
                                    "reason": "Accessible role/name selector.",
                                }
                            ],
                        }
                    ],
                }
            )
        ],
    )

    export = DomInspectionAgent().export_page_objects(report, tmp_path / "pom")

    assert "pages/app_page.py" in export.files
    assert (tmp_path / "pom" / "pages" / "app_page.py").is_file()
    assert "sign_in_locator" in (tmp_path / "pom" / "pages" / "app_page.py").read_text()


def test_exports_xray_csv_from_json_suite(tmp_path: Path) -> None:
    suite_json = """
    {
      "feature": "Profile",
      "source_summary": "Profile requirements",
      "test_cases": [
        {
          "id": "TC-001",
          "title": "Update display name",
          "objective": "Verify profile update.",
          "test_type": "functional",
          "priority": "high",
          "steps": [
            {"step": 1, "action": "Save a new name", "expected_result": "Name is saved"}
          ],
          "expected_result": "Profile is updated."
        }
      ]
    }
    """

    export = TestManagementExportAgent().export(suite_json, "xray", tmp_path)

    assert export.row_count == 1
    assert "xray-import.csv" in export.files
    assert "Update display name" in (tmp_path / "xray-import.csv").read_text()
