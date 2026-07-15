from pathlib import Path

from qa_agents.sources.figma import FigmaSourceLoader
from qa_agents.sources.files import FileSourceLoader


def test_loads_markdown(tmp_path: Path) -> None:
    source = tmp_path / "prd.md"
    source.write_text("# Checkout\nUsers can pay by card.")

    material = FileSourceLoader().load(source)

    assert material.kind == "document"
    assert "pay by card" in material.content


def test_parses_figma_node_url() -> None:
    key, node_id = FigmaSourceLoader._parse_url(
        "https://www.figma.com/design/abc123/Product?node-id=12-34"
    )

    assert key == "abc123"
    assert node_id == "12:34"
