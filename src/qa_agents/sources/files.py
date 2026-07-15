from __future__ import annotations

import base64
import csv
import json
from pathlib import Path

import yaml
from docx import Document
from pypdf import PdfReader

from qa_agents.models import SourceMaterial


class UnsupportedSourceError(ValueError):
    pass


class FileSourceLoader:
    TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".rst"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def load(self, path: str | Path) -> SourceMaterial:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")

        suffix = source.suffix.lower()
        if suffix in self.TEXT_EXTENSIONS:
            content = source.read_text(encoding="utf-8")
        elif suffix == ".pdf":
            content = "\n\n".join(page.extract_text() or "" for page in PdfReader(source).pages)
        elif suffix == ".docx":
            document = Document(source)
            content = "\n".join(paragraph.text for paragraph in document.paragraphs)
        elif suffix == ".json":
            content = json.dumps(json.loads(source.read_text()), indent=2, ensure_ascii=False)
        elif suffix in {".yaml", ".yml"}:
            content = yaml.safe_dump(yaml.safe_load(source.read_text()), sort_keys=False)
        elif suffix == ".csv":
            with source.open(newline="", encoding="utf-8-sig") as handle:
                content = "\n".join(" | ".join(row) for row in csv.reader(handle))
        elif suffix in self.IMAGE_EXTENSIONS:
            image = base64.b64encode(source.read_bytes()).decode()
            return SourceMaterial(
                name=source.name,
                kind="image",
                content="Analyze the attached product design image as a QA specification.",
                images_base64=[image],
            )
        else:
            documents = {".pdf", ".docx", ".json", ".yaml", ".yml", ".csv"}
            supported = sorted(self.TEXT_EXTENSIONS | self.IMAGE_EXTENSIONS | documents)
            raise UnsupportedSourceError(
                f"Unsupported file type '{suffix}'. Supported: {', '.join(supported)}"
            )

        if not content.strip():
            raise ValueError(f"No readable content found in {source.name}")
        return SourceMaterial(name=source.name, kind="document", content=content)
