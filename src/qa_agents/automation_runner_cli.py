from __future__ import annotations

import argparse
import json
import sys

from qa_agents.automation_runner_agent import AutomationRunnerAgent
from qa_agents.progress import ConsoleProgress
from qa_agents.reporting_agent import ReportingAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run generated Playwright automation test cases.")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Generated Playwright automation project directory.",
    )
    parser.add_argument("--url", required=True, help="Target application URL to test.")
    parser.add_argument("--headed", action="store_true", help="Run with the browser visible.")
    parser.add_argument("--timeout", type=int, default=600, help="Maximum run time in seconds.")
    parser.add_argument(
        "--pytest-arg",
        action="append",
        default=[],
        help=(
            "Extra pytest argument. Repeat for multiple arguments, for example "
            "--pytest-arg -k --pytest-arg login."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    progress = ConsoleProgress("RunnerAgent")
    try:
        progress.update(5, "Validating generated automation project")
        progress.update(20, "Starting pytest execution")
        result = AutomationRunnerAgent().run(
            project_dir=args.project_dir,
            target_url=args.url,
            headed=args.headed,
            timeout_seconds=args.timeout,
            pytest_args=args.pytest_arg,
        )
        progress.update(80, "Creating execution report")
        report = ReportingAgent().generate(result)
        progress.update(92, "Analyzing self-healing recommendations")
        progress.complete("Automation run complete")
        print(
            json.dumps(
                {
                    "result": result.model_dump(mode="json"),
                    "report": report.model_dump(mode="json"),
                },
                indent=2,
            )
        )
        if result.status.value != "passed":
            raise SystemExit(1)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
