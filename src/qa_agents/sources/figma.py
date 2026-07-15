from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from qa_agents.models import SourceMaterial

FIGMA_URL_PATTERN = re.compile(r"figma\.com/(?:file|design|proto|board|make)/([^/]+)")


class FigmaSourceLoader:
    def __init__(self, access_token: str, timeout_seconds: int = 60) -> None:
        if not access_token:
            raise ValueError("FIGMA_ACCESS_TOKEN is required for Figma URLs")
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds

    def load(self, figma_url: str) -> SourceMaterial:
        file_key, requested_node = self._parse_url(figma_url)
        query = {"depth": 6}
        if requested_node:
            query["ids"] = requested_node
        file_data = self._get_json(f"https://api.figma.com/v1/files/{file_key}?{urlencode(query)}")

        document = file_data.get("document", {})
        text_lines: list[str] = [
            f"Figma file: {file_data.get('name', 'Untitled')}",
            f"Last modified: {file_data.get('lastModified', 'unknown')}",
            "Visible design structure:",
        ]
        frame_ids: list[str] = []
        self._summarize_node(document, text_lines, frame_ids, depth=0)

        image_ids = [requested_node] if requested_node else frame_ids[:4]
        images = self._render_nodes(file_key, [node_id for node_id in image_ids if node_id])
        return SourceMaterial(
            name=file_data.get("name", file_key),
            kind="figma",
            content="\n".join(text_lines),
            images_base64=images,
        )

    @staticmethod
    def _parse_url(figma_url: str) -> tuple[str, str | None]:
        match = FIGMA_URL_PATTERN.search(figma_url)
        if not match:
            raise ValueError(
                "Invalid Figma URL. Expected a /design/, /file/, /proto/, /board/, or /make/ URL."
            )
        query = parse_qs(urlparse(figma_url).query)
        node_id = query.get("node-id", [None])[0]
        if node_id:
            node_id = node_id.replace("-", ":")
        return match.group(1), node_id

    def _summarize_node(
        self,
        node: dict[str, Any],
        lines: list[str],
        frame_ids: list[str],
        depth: int,
    ) -> None:
        node_type = node.get("type", "UNKNOWN")
        name = node.get("name", "Unnamed")
        visible = node.get("visible", True)
        if visible and node_type not in {"DOCUMENT", "CANVAS", "GROUP"}:
            details = [f"{'  ' * depth}- {node_type}: {name}"]
            if node_type == "TEXT" and node.get("characters"):
                details.append(f'text={json.dumps(node["characters"], ensure_ascii=False)}')
            if node.get("componentProperties"):
                details.append(f"properties={json.dumps(node['componentProperties'], ensure_ascii=False)}")
            if node.get("actions"):
                details.append(f"actions={json.dumps(node['actions'], ensure_ascii=False)}")
            lines.append(" | ".join(details))
        if visible and node_type in {"FRAME", "COMPONENT", "SECTION"} and node.get("id"):
            frame_ids.append(node["id"])
        for child in node.get("children", []):
            self._summarize_node(child, lines, frame_ids, min(depth + 1, 8))

    def _render_nodes(self, file_key: str, node_ids: list[str]) -> list[str]:
        if not node_ids:
            return []
        params = urlencode({"ids": ",".join(node_ids), "format": "png", "scale": 1})
        rendered = self._get_json(f"https://api.figma.com/v1/images/{file_key}?{params}")
        images: list[str] = []
        for image_url in rendered.get("images", {}).values():
            if not image_url:
                continue
            with urlopen(image_url, timeout=self.timeout_seconds) as response:
                images.append(base64.b64encode(response.read()).decode())
        return images

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"X-Figma-Token": self.access_token})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode())
