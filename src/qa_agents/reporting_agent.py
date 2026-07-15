from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from qa_agents.models import AutomationRunResult, AutomationRunStatus, ExecutionReport
from qa_agents.self_healing_agent import SelfHealingAgent

SUMMARY_PATTERNS = [
    re.compile(
        r"(?P<failed>\d+) failed, (?P<passed>\d+) passed",
        re.IGNORECASE,
    ),
    re.compile(r"(?P<passed>\d+) passed", re.IGNORECASE),
    re.compile(r"(?P<failed>\d+) failed", re.IGNORECASE),
]


class ReportingAgent:
    """Create an execution report from an automation runner result."""

    def __init__(self, healing_agent: SelfHealingAgent | None = None) -> None:
        self.healing_agent = healing_agent or SelfHealingAgent()

    def generate(self, result: AutomationRunResult) -> ExecutionReport:
        passed, failed = _parse_test_counts(result.stdout, result.stderr)
        total = None if passed is None and failed is None else (passed or 0) + (failed or 0)
        findings = _findings(result)
        healing = self.healing_agent.analyze(result)
        if healing:
            findings.append(f"{len(healing)} locator-related failure signal(s) need review.")

        report = ExecutionReport(
            status=result.status,
            target_url=result.target_url,
            project_dir=result.project_dir,
            command=result.command,
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            summary=_summary(result.status, passed, failed, result.duration_seconds),
            findings=findings,
            self_healing=healing,
            run_report_markdown_path=result.report_markdown_path,
        )
        return _write_report(result, report)


def _parse_test_counts(stdout: str, stderr: str) -> tuple[int | None, int | None]:
    output = "\n".join((stdout or "", stderr or ""))
    passed: int | None = None
    failed: int | None = None
    for pattern in SUMMARY_PATTERNS:
        for match in pattern.finditer(output):
            if "passed" in match.groupdict() and match.groupdict().get("passed") is not None:
                passed = int(match.group("passed"))
            if "failed" in match.groupdict() and match.groupdict().get("failed") is not None:
                failed = int(match.group("failed"))
    return passed, failed


def _findings(result: AutomationRunResult) -> list[str]:
    findings: list[str] = []
    if result.status == AutomationRunStatus.PASSED:
        findings.append("Automation execution completed successfully.")
    elif result.status == AutomationRunStatus.TIMEOUT:
        findings.append("Execution timed out before pytest completed.")
    elif result.status == AutomationRunStatus.ERROR:
        findings.append("Runner failed before pytest could complete.")
    else:
        findings.append("One or more automated tests failed.")

    if result.stderr.strip():
        findings.append("stderr contains additional diagnostic output.")
    if result.report_markdown_path:
        findings.append(f"Raw runner report: {result.report_markdown_path}")
    return findings


def _summary(
    status: AutomationRunStatus,
    passed: int | None,
    failed: int | None,
    duration_seconds: float,
) -> str:
    counts = []
    if passed is not None:
        counts.append(f"{passed} passed")
    if failed is not None:
        counts.append(f"{failed} failed")
    count_text = ", ".join(counts) if counts else "test count unavailable"
    return f"Run {status.value} in {duration_seconds}s with {count_text}."


def _write_report(result: AutomationRunResult, report: ExecutionReport) -> ExecutionReport:
    root = Path(result.project_dir)
    report_dir = root / "test-results"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"autoai-execution-report-{stamp}.json"
    markdown_path = report_dir / f"autoai-execution-report-{stamp}.md"
    updated = report.model_copy(
        update={
            "report_json_path": str(json_path),
            "report_markdown_path": str(markdown_path),
        }
    )
    json_path.write_text(json.dumps(updated.model_dump(mode="json"), indent=2), encoding="utf-8")
    markdown_path.write_text(_to_markdown(updated), encoding="utf-8")
    return updated


def _to_markdown(report: ExecutionReport) -> str:
    findings = "\n".join(f"- {item}" for item in report.findings) or "- None"
    test_counts = (
        f"{report.total_tests if report.total_tests is not None else 'n/a'} total, "
        f"{report.passed_tests if report.passed_tests is not None else 'n/a'} passed, "
        f"{report.failed_tests if report.failed_tests is not None else 'n/a'} failed"
    )
    healing = "\n".join(
        (
            f"- Failed locator: `{item.failed_locator or 'unknown'}`\n"
            f"  Context: {item.failure_context}\n"
            f"  Suggested locators: {_locator_list(item.suggested_locators)}\n"
            f"  Recommendation: {item.recommendation}"
        )
        for item in report.self_healing
    ) or "- No locator healing suggestions."
    return f"""# AutoAI execution report

- Status: {report.status.value}
- Target URL: {report.target_url}
- Project: `{report.project_dir}`
- Command: `{" ".join(report.command)}`
- Exit code: {report.exit_code if report.exit_code is not None else "n/a"}
- Duration: {report.duration_seconds}s
- Tests: {test_counts}

## Summary

{report.summary}

## Findings

{findings}

## Self-Healing Review

{healing}
"""


def _locator_list(locators: list[str]) -> str:
    return ", ".join(f"`{locator}`" for locator in locators) or "n/a"
