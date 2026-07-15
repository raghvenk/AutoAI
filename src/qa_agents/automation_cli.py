from __future__ import annotations

import argparse
import json
import sys

from qa_agents.automation_agent import AutomationAgent
from qa_agents.automation_exporters import export_automation_project
from qa_agents.ollama import OllamaError
from qa_agents.progress import ConsoleProgress


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Playwright automation from QA test cases.")
    parser.add_argument("--url", required=True, help="Target application URL to test.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--test-cases", help="Markdown or JSON test-case file.")
    source.add_argument("--text", help="Test cases provided directly as text.")
    parser.add_argument(
        "--instructions",
        help="Extra automation guidance, credentials notes, or selector strategy.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="output/automation",
        help="Directory for generated project.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = AutomationAgent()
    progress = ConsoleProgress("AutomationAgent")
    try:
        progress.update(5, "Preparing automation request")
        if args.test_cases:
            progress.update(20, "Loading test-case file")
            suite = agent.from_file(args.url, args.test_cases, args.instructions)
        else:
            progress.update(20, "Loading pasted test cases")
            suite = agent.from_text(args.url, args.text, args.instructions)
        progress.update(85, "Exporting Playwright project")
        path = export_automation_project(suite, args.output_dir)
        progress.complete("Automation project generated")
        print(json.dumps({"status": "ok", "tests": len(suite.tests), "output_dir": str(path)}))
    except (ValueError, FileNotFoundError, OllamaError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
