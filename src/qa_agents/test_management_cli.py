from __future__ import annotations

import argparse
from pathlib import Path

from qa_agents.test_management_agent import TestManagementExportAgent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export AutoAI test cases for Xray, Zephyr, or TestRail imports."
    )
    parser.add_argument("test_cases", help="Path to generated test cases in JSON, Markdown, CSV, or text.")
    parser.add_argument("--tool", choices=["xray", "zephyr", "testrail"], default="xray")
    parser.add_argument("--output-dir", default="output/test-management-cli")
    args = parser.parse_args()

    input_path = Path(args.test_cases)
    if not input_path.is_file():
        raise FileNotFoundError(f"Test case file not found: {input_path}")

    output_dir = Path(args.output_dir)
    export = TestManagementExportAgent().export(
        input_path.read_text(encoding="utf-8"),
        args.tool,
        output_dir,
    )
    print(f"Exported {export.row_count} test case row(s) to {output_dir}")


if __name__ == "__main__":
    main()
