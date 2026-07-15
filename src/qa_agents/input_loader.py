from __future__ import annotations

from pathlib import Path

from qa_agents.config import Settings
from qa_agents.models import SourceMaterial
from qa_agents.sources import FigmaSourceLoader, FileSourceLoader


def load_sources_from_inputs(
    settings: Settings,
    files: list[str | Path] | None = None,
    figma_url: str | None = None,
    text: str | None = None,
) -> list[SourceMaterial]:
    loader = FileSourceLoader()
    sources = [loader.load(Path(path)) for path in (files or [])]
    if text and text.strip():
        sources.append(SourceMaterial(name="Manual instructions", kind="text", content=text.strip()))
    if figma_url and figma_url.strip():
        sources.append(FigmaSourceLoader(settings.figma_access_token or "").load(figma_url.strip()))
    return sources
