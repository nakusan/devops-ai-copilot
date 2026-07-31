"""PDF 解析（pypdf 文本层）。"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def parse_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(f"\n<!-- page:{i + 1} -->\n{text}")
    return "\n".join(pages)
