from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path

from pydantic import ValidationError

from qa_agents.models import TestCase, TestCaseSuite, TestManagementExport, TestManagementTool


class TestManagementExportAgent:
    """Export AutoAI test cases into common test-management import formats."""

    def export(
        self,
        test_cases_text: str,
        tool: str = "xray",
        output_dir: str | Path | None = None,
    ) -> TestManagementExport:
        test_cases_text = test_cases_text.strip()
        if not test_cases_text:
            raise ValueError("Test cases are required.")

        selected_tool = TestManagementTool(tool.lower())
        suite = _parse_suite(test_cases_text)
        rows = [_row_for_case(test) for test in suite.test_cases]
        files = _render_files(selected_tool, suite, rows)

        if output_dir:
            root = Path(output_dir)
            root.mkdir(parents=True, exist_ok=True)
            for name, content in files.items():
                (root / name).write_text(content, encoding="utf-8")

        return TestManagementExport(
            tool=selected_tool,
            source_summary=suite.source_summary,
            row_count=len(rows),
            files=files,
        )


def _parse_suite(text: str) -> TestCaseSuite:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and "suite" in payload:
            payload = payload["suite"]
        return TestCaseSuite.model_validate(payload)
    except (json.JSONDecodeError, ValidationError):
        return _suite_from_markdown(text)


def _suite_from_markdown(text: str) -> TestCaseSuite:
    cases: list[dict[str, object]] = []
    pattern = re.compile(r"(TC-\d{3,})[:\s-]+(.+)", re.IGNORECASE)
    matches = list(pattern.finditer(text))
    for index, match in enumerate(matches, start=1):
        start = match.end()
        end = matches[index].start() if index < len(matches) else len(text)
        body = text[start:end].strip()
        cases.append(
            {
                "id": match.group(1).upper(),
                "title": match.group(2).strip().splitlines()[0],
                "objective": _first_value(body, "Objective") or match.group(2).strip(),
                "test_type": "functional",
                "priority": (_first_value(body, "Priority") or "medium").lower(),
                "steps": _steps_from_body(body),
                "expected_result": _first_value(body, "Expected result") or "Expected behavior is observed.",
            }
        )
    if not cases:
        cases.append(
            {
                "id": "TC-001",
                "title": "Imported manual test case",
                "objective": "Imported from free-form test case text.",
                "test_type": "functional",
                "priority": "medium",
                "steps": [
                    {
                        "step": 1,
                        "action": text[:500],
                        "expected_result": "Expected behavior is observed.",
                    }
                ],
                "expected_result": "Expected behavior is observed.",
            }
        )
    return TestCaseSuite(
        feature="Imported test cases",
        source_summary="Imported from Markdown or free-form test case text.",
        test_cases=[TestCase.model_validate(case) for case in cases],
    )


def _first_value(body: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}\s*:\s*(.+)", body, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _steps_from_body(body: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, line in enumerate(re.findall(r"(?:^|\n)\s*(?:\d+\.|-)\s+(.+)", body), start=1):
        rows.append(
            {
                "step": index,
                "action": line.strip(),
                "expected_result": "Expected behavior is observed.",
            }
        )
    return rows or [
        {
            "step": 1,
            "action": "Execute the documented test steps.",
            "expected_result": "Expected result occurs.",
        }
    ]


def _row_for_case(test: TestCase) -> dict[str, str]:
    steps = "\n".join(f"{step.step}. {step.action}" for step in test.steps)
    expected = "\n".join(f"{step.step}. {step.expected_result}" for step in test.steps)
    return {
        "id": test.id,
        "title": test.title,
        "objective": test.objective,
        "priority": test.priority.value,
        "type": test.test_type.value,
        "preconditions": "\n".join(test.preconditions),
        "steps": steps,
        "expected_result": test.expected_result or expected,
        "step_expected_results": expected,
        "test_data": "\n".join(test.test_data),
        "labels": ",".join(test.tags),
        "requirement_refs": ",".join(test.requirement_refs),
    }


def _render_files(
    tool: TestManagementTool,
    suite: TestCaseSuite,
    rows: list[dict[str, str]],
) -> dict[str, str]:
    if tool == TestManagementTool.XRAY:
        return {
            "xray-import.csv": _csv(
                [
                    "Issue ID",
                    "Test Summary",
                    "Test Type",
                    "Priority",
                    "Action",
                    "Data",
                    "Expected Result",
                    "Requirement",
                    "Labels",
                ],
                [
                    {
                        "Issue ID": row["id"],
                        "Test Summary": row["title"],
                        "Test Type": "Manual",
                        "Priority": row["priority"],
                        "Action": row["steps"],
                        "Data": row["test_data"],
                        "Expected Result": row["expected_result"],
                        "Requirement": row["requirement_refs"],
                        "Labels": row["labels"],
                    }
                    for row in rows
                ],
            )
        }
    if tool == TestManagementTool.ZEPHYR:
        return {
            "zephyr-import.csv": _csv(
                ["Name", "Objective", "Precondition", "Priority", "Labels", "Test Script (Step-by-Step)"],
                [
                    {
                        "Name": row["title"],
                        "Objective": row["objective"],
                        "Precondition": row["preconditions"],
                        "Priority": row["priority"],
                        "Labels": row["labels"],
                        "Test Script (Step-by-Step)": (
                            f"{row['steps']}\n\nExpected:\n{row['step_expected_results']}"
                        ),
                    }
                    for row in rows
                ],
            )
        }
    return {
        "testrail-import.csv": _csv(
            [
                "Section",
                "Title",
                "Priority",
                "Type",
                "Preconditions",
                "Steps",
                "Expected Result",
                "References",
            ],
            [
                {
                    "Section": suite.feature,
                    "Title": row["title"],
                    "Priority": row["priority"],
                    "Type": row["type"],
                    "Preconditions": row["preconditions"],
                    "Steps": row["steps"],
                    "Expected Result": row["expected_result"],
                    "References": row["requirement_refs"],
                }
                for row in rows
            ],
        )
    }


def _csv(fieldnames: list[str], rows: list[dict[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
