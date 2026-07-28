"""RetrieverService 单元测试。"""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.rag.models.chunk_hit import ChunkHit
from app.rag.retrieval.retriever import RetrieverService


@pytest.mark.asyncio
async def test_retriever_filters_by_score_threshold() -> None:
    svc = RetrieverService()
    hits = [
        ChunkHit(
            chunk_id=UUID("11111111-1111-1111-1111-111111111111"),
            document_id=UUID("22222222-2222-2222-2222-222222222222"),
            document_title="doc",
            content="content",
            score=0.95,
        ),
        ChunkHit(
            chunk_id=UUID("33333333-3333-3333-3333-333333333333"),
            document_id=UUID("22222222-2222-2222-2222-222222222222"),
            document_title="doc",
            content="low",
            score=0.5,
        ),
    ]
    with (
        patch.object(svc._embedder, "embed_query", new=AsyncMock(return_value=[0.1] * 1536)),
        patch.object(svc._store, "similarity_search", new=AsyncMock(return_value=hits)),
    ):
        result = await svc.retrieve("query", top_k=5, score_threshold=0.7, team_id=1)
    assert len(result) == 1
    assert result[0].score == 0.95


@pytest.mark.asyncio
async def test_retriever_requires_team_id() -> None:
    svc = RetrieverService()
    result = await svc.retrieve("query", team_id=None)
    assert result == []
