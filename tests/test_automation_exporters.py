from pathlib import Path

from qa_agents.automation_exporters import export_automation_project
from qa_agents.models import AutomationSuite


def test_exports_playwright_project(tmp_path: Path) -> None:
    suite = AutomationSuite.model_validate(
        {
            "target_url": "https://staging.example.test",
            "tests": [
                {
                    "id": "TC-001",
                    "title": "Successful login",
                    "priority": "high",
                    "test_data": [
                        {
                            "name": "email",
                            "value": "qa.user@example.test",
                            "description": "Synthetic email.",
                        }
                    ],
                    "steps": [
                        {
                            "step": 1,
                            "action": "fill",
                            "description": "Enter email.",
                            "locator": "get_by_label('Email')",
                            "value": "{{email}}",
                            "expected_result": "Email entered.",
                        },
                        {
                            "step": 2,
                            "action": "expect_visible",
                            "description": "Dashboard appears.",
                            "locator": "Dashboard",
                            "expected_result": "Dashboard visible.",
                        },
                    ],
                }
            ],
        }
    )

    output = export_automation_project(suite, tmp_path / "automation")

    assert (output / "requirements.txt").is_file()
    assert (output / "conftest.py").is_file()
    assert (output / "autoai_self_healing.py").is_file()
    generated_test = (output / "tests" / "test_generated.py").read_text(encoding="utf-8")
    helper = (output / "autoai_self_healing.py").read_text(encoding="utf-8")
    assert "autoai_fill(page, page.get_by_label('Email'), data['email'], 'Enter email.')" in generated_test
    assert (
        "autoai_expect_visible(page, page.get_by_text('Dashboard'), 'Dashboard appears.')"
        in generated_test
    )
    assert "_is_post_logout_protected_action" in helper
    assert "_exercise_protected_route_after_logout" in helper
    assert "_navigate_or_skip_section" in helper
    assert "_exercise_cross_account_access" in helper
