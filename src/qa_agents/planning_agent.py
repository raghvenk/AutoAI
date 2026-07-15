from __future__ import annotations

from pydantic import ValidationError

from qa_agents.config import Settings, get_settings
from qa_agents.models import SourceMaterial, TestPlan
from qa_agents.ollama import OllamaClient, OllamaError
from qa_agents.prompts import TEST_PLANNING_SYSTEM_PROMPT, build_planning_user_prompt
from qa_agents.source_utils import combine_sources


class TestPlanningAgent:
    """Create extensive QA test plans from requirements and design material."""

    __test__ = False

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

    def generate(self, sources: list[SourceMaterial], instructions: str | None = None) -> TestPlan:
        if not sources:
            raise ValueError("At least one source is required for test planning.")
        source_text = combine_sources(sources, self.settings.qa_agent_max_source_chars)
        content = self.llm.chat(
            system_prompt=TEST_PLANNING_SYSTEM_PROMPT,
            user_prompt=build_planning_user_prompt(source_text, instructions),
            response_schema=TestPlan.model_json_schema(),
        )
        try:
            return TestPlan.model_validate_json(content)
        except ValidationError as exc:
            raise OllamaError(f"Ollama returned invalid test-plan JSON: {exc}") from exc
