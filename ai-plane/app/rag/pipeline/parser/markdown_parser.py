"""Markdown 解析：MVP 直读 UTF-8（可选剥 front matter）。"""

from __future__ import annotations

import re
from pathlib import Path

_FRONT_MATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def parse_markdown(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return _FRONT_MATTER.sub("", text, count=1)
