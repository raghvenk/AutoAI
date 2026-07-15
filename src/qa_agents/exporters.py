from __future__ import annotations

import csv
import json
from pathlib import Path

from qa_agents.models import TestCaseSuite


def export_suite(suite: TestCaseSuite, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(json.dumps(suite.model_dump(mode="json"), indent=2), encoding="utf-8")
    elif suffix in {".md", ".markdown"}:
        path.write_text(_to_markdown(suite), encoding="utf-8")
    elif suffix == ".csv":
        _to_csv(suite, path)
    else:
        raise ValueError("Output extension must be .json, .md, or .csv")
    return path


def _to_markdown(suite: TestCaseSuite) -> str:
    lines = [f"# {suite.feature}", "", suite.source_summary, ""]
    if suite.assumptions:
        lines.extend(["## Assumptions", "", *[f"- {item}" for item in suite.assumptions], ""])
    if suite.open_questions:
        lines.extend(["## Open questions", "", *[f"- {item}" for item in suite.open_questions], ""])
    lines.extend(["## Test cases", ""])
    for test in suite.test_cases:
        lines.extend(
            [
                f"### {test.id}: {test.title}",
                "",
                f"- Type: {test.test_type.value}",
                f"- Priority: {test.priority.value}",
                f"- Automation candidate: {'Yes' if test.automation_candidate else 'No'}",
                f"- Objective: {test.objective}",
                f"- Requirement refs: {', '.join(test.requirement_refs) or 'None'}",
                "",
                "| # | Action | Expected result |",
                "|---:|---|---|",
            ]
        )
        for step in test.steps:
            action = step.action.replace("|", "\\|")
            expected = step.expected_result.replace("|", "\\|")
            lines.append(f"| {step.step} | {action} | {expected} |")
        lines.extend(["", f"Overall expected result: {test.expected_result}", ""])
    return "\n".join(lines)


def suite_to_markdown(suite: TestCaseSuite) -> str:
    """Render a suite as Markdown without writing a file."""
    return _to_markdown(suite)


def _to_csv(suite: TestCaseSuite, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id", "title", "objective", "requirement_refs", "test_type", "priority",
                "preconditions", "test_data", "steps", "expected_result", "tags", "automation_candidate",
            ],
        )
        writer.writeheader()
        for test in suite.test_cases:
            row = test.model_dump(mode="json")
            row["requirement_refs"] = "; ".join(test.requirement_refs)
            row["preconditions"] = "; ".join(test.preconditions)
            row["test_data"] = "; ".join(test.test_data)
            row["steps"] = json.dumps(row["steps"], ensure_ascii=False)
            row["tags"] = "; ".join(test.tags)
            writer.writerow(row)
