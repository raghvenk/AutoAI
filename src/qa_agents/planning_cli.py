from __future__ import annotations

import argparse
import json
import sys

from qa_agents.artifact_exporters import export_artifact
from qa_agents.config import get_settings
from qa_agents.input_loader import load_sources_from_inputs
from qa_agents.ollama import OllamaError
from qa_agents.planning_agent import TestPlanningAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a QA test plan from requirements or designs.")
    parser.add_argument("--source", action="append", help="BRD/PRD/design file. Repeat for multiple files.")
    parser.add_argument("--figma-url", help="Figma file or node URL.")
    parser.add_argument("--text", help="Manual requirement instructions.")
    parser.add_argument("--instructions", help="Extra planning guidance.")
    parser.add_argument("--output", "-o", default="output/test-plan.md", help=".md or .json output.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    try:
        sources = load_sources_from_inputs(settings, args.source, args.figma_url, args.text)
        plan = TestPlanningAgent(settings).generate(sources, args.instructions)
        path = export_artifact(plan, args.output)
        print(json.dumps({"status": "ok", "output": str(path)}))
    except (ValueError, FileNotFoundError, OllamaError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
