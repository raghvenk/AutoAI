from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from qa_agents.dom_agent import DomInspectionAgent
from qa_agents.web import _dom_report_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a web app DOM and export Page Object Model files.")
    parser.add_argument("target_url")
    parser.add_argument("--output", default="output/dom-cli", help="Directory for DOM report and POM files.")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    agent = DomInspectionAgent()
    report = agent.inspect(args.target_url, args.max_pages, args.headed)
    agent.export_page_objects(report, output / "pom")
    (output / "dom-report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    (output / "dom-report.md").write_text(_dom_report_markdown(report), encoding="utf-8")
    with zipfile.ZipFile(output / "page-object-model.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in (output / "pom").rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(output / "pom"))
    print(output)


if __name__ == "__main__":
    main()
