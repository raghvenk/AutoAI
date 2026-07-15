from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from qa_agents.config import get_settings
from qa_agents.test_case_agent import TestCaseAgent

mcp = FastMCP("AutoAI QA Agents")


@mcp.tool()
def check_ollama() -> dict[str, Any]:
    """Check the configured Ollama server and list locally available models."""
    agent = TestCaseAgent()
    return agent.llm.health()


@mcp.tool()
def generate_test_cases_from_text(requirements: str, instructions: str | None = None) -> dict[str, Any]:
    """Generate traceable QA test cases from PRD or requirement text."""
    return TestCaseAgent().from_text(requirements, instructions=instructions).model_dump(mode="json")


@mcp.tool()
def generate_test_cases_from_file(path: str, instructions: str | None = None) -> dict[str, Any]:
    """Generate QA test cases from a local PDF, DOCX, text, Markdown, JSON, YAML, CSV, or image."""
    return TestCaseAgent().from_files([path], instructions).model_dump(mode="json")


@mcp.tool()
def generate_test_cases_from_figma(figma_url: str, instructions: str | None = None) -> dict[str, Any]:
    """Generate QA test cases from a Figma file or node URL."""
    return TestCaseAgent().from_figma(figma_url, instructions).model_dump(mode="json")


@mcp.resource("config://qa-agent")
def configured_agent() -> dict[str, Any]:
    """Expose non-secret runtime configuration."""
    settings = get_settings()
    return {
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "ollama_vision_model": settings.ollama_vision_model,
        "ollama_timeout_seconds": settings.ollama_timeout_seconds,
        "ollama_context_window": settings.ollama_context_window,
        "max_source_chars": settings.qa_agent_max_source_chars,
        "figma_configured": bool(settings.figma_access_token),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
