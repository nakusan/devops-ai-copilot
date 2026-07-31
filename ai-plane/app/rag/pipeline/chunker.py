"""Recursive character splitter（固定长度 + overlap）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings
from app.rag.models.chunk import TextChunk


@dataclass
class ChunkConfig:
    chunk_size: int = field(default_factory=lambda: settings.chunk_size)
    chunk_overlap: int = field(default_factory=lambda: settings.chunk_overlap)
    separators: list[str] = field(
        default_factory=lambda: ["\n\n", "\n", "。", " ", ""]
    )


def chunk_text(text: str, cfg: ChunkConfig | None = None, *, base_metadata: dict | None = None) -> list[TextChunk]:
    """按分隔符递归切分，保证每块 ≤ chunk_size，相邻 overlap。"""
    cfg = cfg or ChunkConfig()
    meta = base_metadata or {}
    if not text:
        return []
    pieces = _split(text, cfg.separators, cfg.chunk_size)
    # 合并过小片段并施加 overlap
    chunks: list[TextChunk] = []
    buf = ""
    for piece in pieces:
        if not buf:
            buf = piece
        elif len(buf) + len(piece) <= cfg.chunk_size:
            buf += piece
        else:
            chunks.append(TextChunk(chunk_index=len(chunks), content=buf, metadata=dict(meta)))
            # overlap：从上一块末尾取 overlap 字符作为下一块前缀
            overlap = buf[-cfg.chunk_overlap :] if cfg.chunk_overlap > 0 else ""
            buf = overlap + piece
            # 若仍超长，硬切
            while len(buf) > cfg.chunk_size:
                chunks.append(
                    TextChunk(
                        chunk_index=len(chunks),
                        content=buf[: cfg.chunk_size],
                        metadata=dict(meta),
                    )
                )
                buf = buf[cfg.chunk_size - cfg.chunk_overlap :]
    if buf.strip():
        chunks.append(TextChunk(chunk_index=len(chunks), content=buf, metadata=dict(meta)))
    return chunks


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
        # 保留分隔符语义：除最后一段外拼回 sep
        segment = part + (sep if i < len(parts) - 1 else "")
        if len(segment) <= chunk_size:
            if segment:
                out.append(segment)
        else:
            out.extend(_split(segment, rest, chunk_size))
    return out
