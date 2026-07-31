"""文本清洗：NFKC + 空白归一。"""

from __future__ import annotations

import re
import unicodedata


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
