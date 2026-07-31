"""按 MIME / 扩展名选择解析器。"""

from __future__ import annotations

from pathlib import Path

from app.rag.pipeline.parser.markdown_parser import parse_markdown
from app.rag.pipeline.parser.pdf_parser import parse_pdf
from app.rag.pipeline.parser.text_parser import parse_text


def parse_document(path: Path, mime_type: str | None = None) -> str:
    mime = (mime_type or "").lower()
    suffix = path.suffix.lower()
    if "pdf" in mime or suffix == ".pdf":
        return parse_pdf(path)
    if "markdown" in mime or suffix in {".md", ".markdown"}:
        return parse_markdown(path)
    return parse_text(path)
