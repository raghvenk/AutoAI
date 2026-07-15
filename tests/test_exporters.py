from pathlib import Path

from qa_agents.exporters import export_suite
from qa_agents.models import TestCaseSuite as Suite


def test_exports_all_supported_formats(tmp_path: Path) -> None:
    suite = Suite.model_validate(
        {
            "feature": "Checkout",
            "source_summary": "A checkout flow.",
            "test_cases": [
                {
                    "id": "TC-001",
                    "title": "Pay by card",
                    "objective": "Complete payment.",
                    "test_type": "functional",
                    "priority": "high",
                    "steps": [
                        {
                            "step": 1,
                            "action": "Submit card | details",
                            "expected_result": "Payment succeeds | receipt appears",
                        }
                    ],
                    "expected_result": "The order is placed.",
                }
            ],
        }
    )

    for suffix in ("md", "json", "csv"):
        output = export_suite(suite, tmp_path / f"suite.{suffix}")
        assert output.is_file()
        assert output.stat().st_size > 0
