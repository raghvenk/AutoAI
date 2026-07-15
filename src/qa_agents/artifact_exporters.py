from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from qa_agents.models import DefectSuite, TestDesignSuite, TestPlan


def export_artifact(artifact: BaseModel, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(json.dumps(artifact.model_dump(mode="json"), indent=2), encoding="utf-8")
    elif suffix in {".md", ".markdown"}:
        path.write_text(artifact_to_markdown(artifact), encoding="utf-8")
    else:
        raise ValueError("Output extension must be .json or .md")
    return path


def artifact_to_markdown(artifact: BaseModel) -> str:
    if isinstance(artifact, TestPlan):
        return _plan_to_markdown(artifact)
    if isinstance(artifact, TestDesignSuite):
        return _design_to_markdown(artifact)
    if isinstance(artifact, DefectSuite):
        return _defects_to_markdown(artifact)
    return f"```json\n{json.dumps(artifact.model_dump(mode='json'), indent=2)}\n```\n"


def _plan_to_markdown(plan: TestPlan) -> str:
    lines = [
        f"# Test Plan: {plan.feature}",
        "",
        plan.objective,
        "",
        "## Source summary",
        "",
        plan.source_summary,
    ]
    _extend_list(lines, "Test strategy", plan.test_strategy)
    _extend_list(lines, "Test levels", plan.test_levels)
    _extend_list(lines, "Test types", [item.value for item in plan.test_types])
    if plan.scope:
        lines.extend(["", "## Scope"])
        for item in plan.scope:
            lines.extend(
                [
                    "",
                    f"### {item.area}",
                    "",
                    "In scope:",
                    *[f"- {scope}" for scope in item.in_scope],
                    "",
                    "Out of scope:",
                    *[f"- {scope}" for scope in item.out_of_scope],
                ]
            )
    if plan.environments:
        lines.extend(["", "## Environments"])
        for env in plan.environments:
            lines.extend(["", f"### {env.name}", "", env.purpose])
            _extend_list(lines, "Dependencies", env.dependencies)
    _extend_list(lines, "Entry criteria", plan.entry_criteria)
    _extend_list(lines, "Exit criteria", plan.exit_criteria)
    if plan.risks:
        lines.extend(["", "## Risks"])
        for risk in plan.risks:
            lines.append(f"- {risk.impact.value}: {risk.risk} — Mitigation: {risk.mitigation}")
    _extend_list(lines, "Assumptions", plan.assumptions)
    _extend_list(lines, "Open questions", plan.open_questions)
    _extend_list(lines, "Deliverables", plan.deliverables)
    return "\n".join(lines).strip() + "\n"


def _design_to_markdown(design: TestDesignSuite) -> str:
    lines = [f"# Test Design: {design.feature}", "", design.source_summary]
    _extend_list(lines, "Design approach", design.design_approach)
    if design.scenarios:
        lines.extend(["", "## Design scenarios"])
        for scenario in design.scenarios:
            lines.extend(
                [
                    "",
                    f"### {scenario.id}: {scenario.title}",
                    "",
                    f"- Technique: {scenario.design_technique}",
                    f"- Priority: {scenario.priority.value}",
                    f"- Requirement refs: {', '.join(scenario.requirement_refs) or 'None'}",
                    f"- Data IDs: {', '.join(scenario.data_ids) or 'None'}",
                ]
            )
            _extend_list(lines, "Preconditions", scenario.preconditions)
            _extend_list(lines, "Coverage notes", scenario.coverage_notes)
    if design.test_data:
        lines.extend(["", "## Test data"])
        for data in design.test_data:
            lines.extend(["", f"### {data.id}: {data.purpose}", "", f"- Sensitive: {data.sensitive}"])
            for key, value in data.data.items():
                lines.append(f"- {key}: `{value}`")
            lines.append(f"- Usage: {data.expected_usage}")
    _extend_list(lines, "Assumptions", design.assumptions)
    _extend_list(lines, "Open questions", design.open_questions)
    return "\n".join(lines).strip() + "\n"


def _defects_to_markdown(suite: DefectSuite) -> str:
    lines = ["# Defect Creation Report", "", suite.execution_summary]
    if suite.target_url:
        lines.extend(["", f"Target URL: {suite.target_url}"])
    if suite.defects:
        lines.extend(["", "## Draft defects"])
        for defect in suite.defects:
            lines.extend(
                [
                    "",
                    f"### {defect.id}: {defect.title}",
                    "",
                    f"- Severity: {defect.severity.value}",
                    f"- Priority: {defect.priority.value}",
                    f"- Status: {defect.status.value}",
                    f"- Environment: {defect.environment}",
                    f"- Source test: {defect.source_test or 'Unknown'}",
                    "",
                    f"Expected: {defect.expected_result}",
                    "",
                    f"Actual: {defect.actual_result}",
                ]
            )
            _extend_list(lines, "Reproduction steps", defect.reproduction_steps)
            _extend_list(lines, "Evidence", defect.evidence)
            if defect.suspected_area:
                lines.extend(["", f"Suspected area: {defect.suspected_area}"])
            _extend_list(lines, "Labels", defect.labels)
    _extend_list(lines, "No-defect notes", suite.no_defect_notes)
    return "\n".join(lines).strip() + "\n"


def _extend_list(lines: list[str], title: str, items: list[str]) -> None:
    if items:
        lines.extend(["", f"## {title}", "", *[f"- {item}" for item in items]])
