from __future__ import annotations

import argparse
import json
import sys

from qa_agents.exporters import export_suite
from qa_agents.ollama import OllamaError
from qa_agents.progress import ConsoleProgress
from qa_agents.test_case_agent import TestCaseAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate QA test cases from PRDs or Figma designs.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source", action="append", help="PRD/design file. Repeat for multiple files.")
    source.add_argument("--figma-url", help="Figma file or node URL.")
    source.add_argument("--text", help="Requirements provided directly as text.")
    parser.add_argument("--instructions", help="Extra scope, platform, or coverage instructions.")
    parser.add_argument("--output", "-o", default="output/test-cases.md", help=".md, .json, or .csv output.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = TestCaseAgent()
    progress = ConsoleProgress("TestCaseAgent")
    try:
        progress.update(5, "Preparing source material")
        if args.source:
            progress.update(20, "Loading files")
            suite = agent.from_files(args.source, args.instructions)
        elif args.figma_url:
            progress.update(20, "Loading Figma source")
            suite = agent.from_figma(args.figma_url, args.instructions)
        else:
            progress.update(20, "Loading pasted requirements")
            suite = agent.from_text(args.text, instructions=args.instructions)
        progress.update(85, "Exporting generated test cases")
        path = export_suite(suite, args.output)
        progress.complete("Test cases generated")
        print(json.dumps({"status": "ok", "test_cases": len(suite.test_cases), "output": str(path)}))
    except (ValueError, FileNotFoundError, OllamaError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
