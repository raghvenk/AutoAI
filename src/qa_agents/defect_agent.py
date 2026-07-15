from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from qa_agents.config import Settings, get_settings
from qa_agents.models import AutomationRunResult, DefectSuite, ExecutionReport
from qa_agents.ollama import OllamaClient, OllamaError
from qa_agents.prompts import DEFECT_SYSTEM_PROMPT, build_defect_user_prompt
from qa_agents.source_utils import maybe_truncate_text


class DefectCreationAgent:
    """Create draft defects from execution reports, runner output, or manual failure notes."""

    def __init__(self, settings: Settings | None = None, llm: OllamaClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or OllamaClient(
            base_url=self.settings.ollama_base_url,
            model=self.settings.ollama_model,
            timeout_seconds=self.settings.ollama_timeout_seconds,
            temperature=self.settings.ollama_temperature,
            context_window=self.settings.ollama_context_window,
            max_output_tokens=self.settings.ollama_max_output_tokens,
        )

    def from_text(
        self,
        execution_text: str,
        target_url: str | None = None,
        context: str | None = None,
    ) -> DefectSuite:
        execution_text = maybe_truncate_text(execution_text.strip(), self.settings)
        if not execution_text:
            raise ValueError("Execution report or failure notes are required.")
        content = self.llm.chat(
            system_prompt=DEFECT_SYSTEM_PROMPT,
            user_prompt=build_defect_user_prompt(execution_text, target_url, context),
            response_schema=DefectSuite.model_json_schema(),
        )
        try:
            return DefectSuite.model_validate_json(content)
        except ValidationError as exc:
            raise OllamaError(f"Ollama returned invalid defect JSON: {exc}") from exc

    def from_file(
        self,
        path: str | Path,
        target_url: str | None = None,
        context: str | None = None,
    ) -> DefectSuite:
        report_path = Path(path)
        if not report_path.is_file():
            raise FileNotFoundError(f"Execution report not found: {report_path}")
        return self.from_text(_read_report(report_path), target_url, context)

    def from_execution_report(
        self,
        report: ExecutionReport,
        context: str | None = None,
    ) -> DefectSuite:
        report_text = json.dumps(report.model_dump(mode="json"), indent=2)
        return self.from_text(report_text, report.target_url, context)

    def from_run_result(
        self,
        result: AutomationRunResult,
        context: str | None = None,
    ) -> DefectSuite:
        result_text = json.dumps(result.model_dump(mode="json"), indent=2)
        return self.from_text(result_text, result.target_url, context)


def _read_report(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            return json.dumps(json.loads(text), indent=2)
        except json.JSONDecodeError:
            return text
    return text
