from __future__ import annotations

from qa_agents.config import Settings
from qa_agents.models import SourceMaterial


def combine_sources(sources: list[SourceMaterial], max_chars: int) -> str:
    parts: list[str] = []
    for source in sources:
        parts.append(f"## {source.name} ({source.kind})\n{source.content}")
    text = "\n\n".join(parts).strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[Source truncated because it exceeded QA_AGENT_MAX_SOURCE_CHARS.]"
    return text


def maybe_truncate_text(text: str, settings: Settings) -> str:
    if len(text) <= settings.qa_agent_max_source_chars:
        return text
    return (
        text[: settings.qa_agent_max_source_chars]
        + "\n\n[Source truncated because it exceeded QA_AGENT_MAX_SOURCE_CHARS.]"
    )
