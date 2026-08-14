"""标题感知切块：按 Markdown / 章节号切，超长节回退递归字符切分。

切完后丢掉低信息量块（残留目录、纯页码、分隔线），并写入 heading / page 到 metadata。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import settings
from app.rag.models.chunk import TextChunk
from app.rag.pipeline.cleaner import PAGE_SENTINEL_RE, strip_page_sentinels

_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# 3.1.3 消息中心  或  2 登录；避免把「3. 点击确定」这种步骤句当成标题
_NUM_HEADING = re.compile(
    r"^(?P<num>\d{1,2}(?:\.\d{1,2})+|\d{1,2})\s+"
    r"(?P<title>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9、，.\-（）()]{0,60})$"
)
_SUBSTANTIVE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


@dataclass
class ChunkConfig:
    chunk_size: int = field(default_factory=lambda: settings.chunk_size)
    chunk_overlap: int = field(default_factory=lambda: settings.chunk_overlap)
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", "。", " ", ""])
    min_substantive_chars: int = field(
        default_factory=lambda: settings.chunk_min_substantive_chars
    )
    min_substantive_ratio: float = field(
        default_factory=lambda: settings.chunk_min_substantive_ratio
    )


def chunk_text(
    text: str,
    cfg: ChunkConfig | None = None,
    *,
    base_metadata: dict | None = None,
    stats: dict | None = None,
) -> list[TextChunk]:
    """按标题切节；单节超长时再按分隔符递归切，保证每块大约 ≤ chunk_size。"""
    cfg = cfg or ChunkConfig()
    meta = base_metadata or {}
    if not text or not text.strip():
        if stats is not None:
            stats["dropped"] = 0
        return []

    raw_chunks: list[TextChunk] = []
    for heading_path, section in _iter_sections(text):
        raw_chunks.extend(_chunk_section(section, heading_path, cfg, meta))

    kept: list[TextChunk] = []
    dropped = 0
    for chunk in raw_chunks:
        content, pages = strip_page_sentinels(chunk.content)
        if _is_low_information(content, cfg):
            dropped += 1
            continue
        out_meta = dict(chunk.metadata)
        heading = chunk.metadata.get("heading")
        if heading:
            out_meta["heading"] = heading
        if pages:
            out_meta["page"] = pages[0]
        kept.append(
            TextChunk(chunk_index=len(kept), content=content, metadata=out_meta)
        )
    if stats is not None:
        stats["dropped"] = dropped
    return kept


def _iter_sections(text: str) -> list[tuple[list[str], str]]:
    """把全文拆成 (标题路径, 节文本)。无标题时整篇作为一节。

    `<<<PAGE:N>>>` 表示「之后的内容来自第 N 页」，归入下一节而不是上一节。
    """
    lines = text.splitlines(keepends=True)
    stack: list[tuple[int, str]] = []
    sections: list[tuple[list[str], str]] = []
    buf: list[str] = []
    current_path: list[str] = []

    def flush(lines_to_flush: list[str]) -> None:
        body = "".join(lines_to_flush)
        if body.strip():
            sections.append((list(current_path), body))

    for line in lines:
        heading = _match_heading(line)
        if heading is None:
            buf.append(line)
            continue
        body_lines, trailing = _split_trailing_sentinels(buf)
        flush(body_lines)
        buf = trailing
        level, title = heading
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        current_path = [t for _, t in stack]
        buf.append(line)
    flush(buf)
    return sections


def _split_trailing_sentinels(buf: list[str]) -> tuple[list[str], list[str]]:
    """节末尾的页码哨兵和空行属于下一节。"""
    trail: list[str] = []
    while buf:
        stripped = buf[-1].strip()
        if not stripped or PAGE_SENTINEL_RE.fullmatch(stripped):
            trail.insert(0, buf.pop())
        else:
            break
    return buf, trail


def _match_heading(line: str) -> tuple[int, str] | None:
    raw = line.rstrip("\r\n")
    stripped = raw.strip()
    if not stripped or PAGE_SENTINEL_RE.fullmatch(stripped):
        return None
    atx = _ATX_HEADING.match(stripped)
    if atx:
        return len(atx.group(1)), atx.group(2).strip()
    numbered = _NUM_HEADING.match(stripped)
    if numbered:
        num = numbered.group("num")
        title = f"{num} {numbered.group('title').strip()}"
        level = num.count(".") + 1
        return level, title
    return None


def _chunk_section(
    section: str,
    heading_path: list[str],
    cfg: ChunkConfig,
    base_meta: dict,
) -> list[TextChunk]:
    prefix = f"[{' > '.join(heading_path)}]\n" if heading_path else ""
    meta = dict(base_meta)
    if heading_path:
        meta["heading"] = " > ".join(heading_path)

    budget = cfg.chunk_size - len(prefix)
    if budget < 32:
        # 标题路径本身已经很长：仍附上前缀，按整块大小硬切正文
        budget = cfg.chunk_size

    if len(section) <= budget:
        return [TextChunk(chunk_index=0, content=prefix + section, metadata=meta)]

    windows = _window_chunks(section, budget, cfg.chunk_overlap, cfg.separators)
    return [
        TextChunk(chunk_index=0, content=prefix + piece, metadata=dict(meta))
        for piece in windows
    ]


def _window_chunks(
    text: str, chunk_size: int, overlap: int, separators: list[str]
) -> list[str]:
    pieces = _split(text, separators, chunk_size)
    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if not buf:
            buf = piece
        elif len(buf) + len(piece) <= chunk_size:
            buf += piece
        else:
            chunks.append(buf)
            tail = buf[-overlap:] if overlap > 0 else ""
            buf = tail + piece
            while len(buf) > chunk_size:
                chunks.append(buf[:chunk_size])
                buf = buf[chunk_size - overlap :] if overlap < chunk_size else buf[chunk_size:]
    if buf.strip():
        chunks.append(buf)
    return chunks


def _is_low_information(text: str, cfg: ChunkConfig) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    substantive = _SUBSTANTIVE.findall(stripped)
    if len(substantive) < cfg.min_substantive_chars:
        return True
    ratio = len(substantive) / len(stripped)
    return ratio < cfg.min_substantive_ratio


def _split(text: str, separators: list[str], chunk_size: int) -> list[str]:
    if not separators:
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    sep = separators[0]
    rest = separators[1:]
    if sep == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    parts = text.split(sep)
    out: list[str] = []
    for i, part in enumerate(parts):
        segment = part + (sep if i < len(parts) - 1 else "")
        if len(segment) <= chunk_size:
            if segment:
                out.append(segment)
        else:
            out.extend(_split(segment, rest, chunk_size))
    return out
