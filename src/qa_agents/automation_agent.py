from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from qa_agents.config import Settings, get_settings
from qa_agents.models import AutomationSuite, TestCaseSuite
from qa_agents.ollama import OllamaClient, OllamaError
from qa_agents.prompts import AUTOMATION_SYSTEM_PROMPT, build_automation_user_prompt


class AutomationAgent:
    """Generate an executable browser automation plan from manual test cases."""

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

    def from_file(
        self,
        target_url: str,
        test_cases_path: str | Path,
        instructions: str | None = None,
    ) -> AutomationSuite:
        path = Path(test_cases_path)
        if not path.is_file():
            raise FileNotFoundError(f"Test case file not found: {path}")
        return self.from_text(target_url, _read_test_cases(path), instructions)

    def from_text(
        self,
        target_url: str,
        test_cases_text: str,
        instructions: str | None = None,
    ) -> AutomationSuite:
        target_url = target_url.strip()
        test_cases_text = test_cases_text.strip()
        if not target_url:
            raise ValueError("Target URL is required.")
        if not test_cases_text:
            raise ValueError("Test cases are required.")

        if len(test_cases_text) > self.settings.qa_agent_max_source_chars:
            test_cases_text = (
                test_cases_text[: self.settings.qa_agent_max_source_chars]
                + "\n\n[Source truncated because it exceeded QA_AGENT_MAX_SOURCE_CHARS.]"
            )

        content = self.llm.chat(
            system_prompt=AUTOMATION_SYSTEM_PROMPT,
            user_prompt=build_automation_user_prompt(target_url, test_cases_text, instructions),
            response_schema=AutomationSuite.model_json_schema(),
        )
        try:
            suite = AutomationSuite.model_validate_json(content)
        except ValidationError as exc:
            raise OllamaError(f"Ollama returned invalid automation JSON: {exc}") from exc
        return suite


def _read_test_cases(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
            suite = TestCaseSuite.model_validate(payload)
            return json.dumps(suite.model_dump(mode="json"), indent=2)
        except (json.JSONDecodeError, ValidationError):
            return text
    return text
