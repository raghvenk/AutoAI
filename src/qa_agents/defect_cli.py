from __future__ import annotations

import argparse
import json
import sys

from qa_agents.artifact_exporters import export_artifact
from qa_agents.defect_agent import DefectCreationAgent
from qa_agents.ollama import OllamaError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create draft defects from execution reports or failure notes."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--report", help="Execution report file, JSON or Markdown.")
    source.add_argument("--text", help="Failure notes or raw execution output.")
    parser.add_argument("--url", help="Target application URL.")
    parser.add_argument("--context", help="Extra defect triage context.")
    parser.add_argument("--output", "-o", default="output/defects.md", help=".md or .json output.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = DefectCreationAgent()
    try:
        if args.report:
            defects = agent.from_file(args.report, args.url, args.context)
        else:
            defects = agent.from_text(args.text, args.url, args.context)
        path = export_artifact(defects, args.output)
        print(json.dumps({"status": "ok", "defects": len(defects.defects), "output": str(path)}))
    except (ValueError, FileNotFoundError, OllamaError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
