"""文本清洗：NFKC + 剥目录/页码 + 空白归一。

必须在切块之前做：目录行和正文常混在同一 512 字窗口里，切完再整块丢会误删正文。
页码注释改写成 <<<PAGE:N>>> 哨兵，切块器据此写入 metadata 后再从正文剥掉。
"""

from __future__ import annotations

import re
import unicodedata

# 切块器与清洗器共用；正文里几乎不可能出现这个字面量
PAGE_SENTINEL_RE = re.compile(r"<<<PAGE:(\d+)>>>")

_HTML_PAGE_COMMENT = re.compile(r"<!--\s*page\s*:\s*(\d+)\s*-->", re.IGNORECASE)

# 目录点线：`3.1 首页 ........ 9` 或被 PDF 折行后的 `........ 9`
_TOC_LINE = re.compile(
    r"^(?:.*[.·•…]{4,}\s*\d{1,4}|[.·•…]{4,}\s*\d{1,4})\s*$"
)

# 单独成行的页眉页脚
_PAGE_HEADER_FOOTER = re.compile(
    r"^(?:第\s*\d+\s*页(?:\s*[/\-]\s*共\s*\d+\s*页)?|-+\s*\d+\s*-+)\s*$"
)


def clean(text: str) -> str:
    """归一化并去掉结构噪声，保留页码哨兵供切块器消费。"""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _HTML_PAGE_COMMENT.sub(lambda m: f"\n<<<PAGE:{m.group(1)}>>>\n", text)
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        if PAGE_SENTINEL_RE.fullmatch(stripped):
            kept.append(stripped)
            continue
        if _TOC_LINE.match(stripped) or _PAGE_HEADER_FOOTER.match(stripped):
            continue
        kept.append(line)
    text = "\n".join(kept)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def strip_page_sentinels(text: str) -> tuple[str, list[int]]:
    """从文本取出页码哨兵，返回 (去掉哨兵后的正文, 出现过的页码)。"""
    pages = [int(n) for n in PAGE_SENTINEL_RE.findall(text)]
    cleaned = PAGE_SENTINEL_RE.sub("\n", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    return cleaned, pages
