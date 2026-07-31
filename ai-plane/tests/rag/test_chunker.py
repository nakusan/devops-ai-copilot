"""切块器单元测试。"""

from app.rag.pipeline.chunker import ChunkConfig, chunk_text
from app.rag.pipeline.cleaner import clean


def test_clean_collapses_whitespace():
    assert "a b" in clean("a   b\n\n\n\nc")


def test_chunk_respects_size_and_overlap():
    text = ("段落甲。\n\n" + "字" * 50 + "\n\n") * 20
    chunks = chunk_text(text, ChunkConfig(chunk_size=80, chunk_overlap=10))
    assert len(chunks) >= 2
    assert all(len(c.content) <= 80 + 10 for c in chunks)  # overlap 可能导致略超硬切后的边界
    assert chunks[0].chunk_index == 0
    assert chunks[-1].chunk_index == len(chunks) - 1
