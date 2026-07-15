from __future__ import annotations

from collections.abc import Iterable

from pydantic import ValidationError

from qa_agents.config import Settings, get_settings
from qa_agents.models import SourceMaterial, TestCaseSuite
from qa_agents.ollama import OllamaClient, OllamaError
from qa_agents.prompts import SYSTEM_PROMPT, build_user_prompt
from qa_agents.sources import FigmaSourceLoader, FileSourceLoader


class TestCaseAgent:
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
        self.file_loader = FileSourceLoader()

    def from_text(
        self,
        text: str,
        name: str = "requirements",
        instructions: str | None = None,
    ) -> TestCaseSuite:
        return self.generate([SourceMaterial(name=name, kind="text", content=text)], instructions)

    def from_files(self, paths: Iterable[str], instructions: str | None = None) -> TestCaseSuite:
        return self.generate([self.file_loader.load(path) for path in paths], instructions)

    def from_figma(self, figma_url: str, instructions: str | None = None) -> TestCaseSuite:
        loader = FigmaSourceLoader(self.settings.figma_access_token or "")
        return self.generate([loader.load(figma_url)], instructions)

    def generate(
        self,
        sources: Iterable[SourceMaterial],
        instructions: str | None = None,
    ) -> TestCaseSuite:
        materials = list(sources)
        if not materials:
            raise ValueError("At least one source is required")

        source_text = "\n\n".join(
            f"## Source: {source.name} ({source.kind})\n{source.content}" for source in materials
        )
        if len(source_text) > self.settings.qa_agent_max_source_chars:
            source_text = source_text[: self.settings.qa_agent_max_source_chars]
            source_text += "\n\n[Source truncated at configured character limit]"

        schema = TestCaseSuite.model_json_schema()
        images = [image for source in materials for image in source.images_base64]
        prompt = build_user_prompt(source_text, _image_safe_instructions(instructions, bool(images)))
        model = self.settings.ollama_vision_model if images else self.settings.ollama_model
        raw = self.llm.chat(SYSTEM_PROMPT, prompt, schema, images, model=model)
        return self._validate_or_retry(raw, prompt, schema, images, model)

    def _validate_or_retry(
        self,
        raw: str,
        prompt: str,
        schema: dict,
        images: list[str],
        model: str,
    ) -> TestCaseSuite:
        try:
            return TestCaseSuite.model_validate_json(raw)
        except ValidationError as first_exc:
            compact_prompt = _compact_retry_prompt(prompt, first_exc)
            repaired = self.llm.chat(SYSTEM_PROMPT, compact_prompt, schema, images, model=model)
            try:
                return TestCaseSuite.model_validate_json(repaired)
            except ValidationError as final_exc:
                raise OllamaError(
                    "Ollama returned invalid test-case JSON after retry. "
                    "Try requesting fewer cases or reducing Gherkin verbosity. "
                    f"Validation error: {final_exc}"
                ) from final_exc


def _image_safe_instructions(instructions: str | None, has_images: bool) -> str | None:
    if not has_images:
        return instructions
    extra = (
        "For image-only or screenshot inputs, keep the suite compact: generate 6-10 high-value "
        "test cases, keep steps concise, and avoid long prose so the JSON response is not truncated."
    )
    return f"{instructions}\n\n{extra}" if instructions else extra


def _compact_retry_prompt(original_prompt: str, error: ValidationError) -> str:
    return f"""{original_prompt}

The previous response was not valid JSON and may have been truncated.

Validation error:
{error}

Retry requirements:
- Return valid JSON only, matching the schema.
- Generate at most 8 concise test cases.
- If Gherkin style was requested, keep Given/When/Then text short inside the existing step fields.
- Close every string, array, and object.
- Do not include markdown fences or commentary.
"""
