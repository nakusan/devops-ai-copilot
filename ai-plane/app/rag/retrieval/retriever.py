"""在线检索入口 — 供 LangGraph RetrieveNode 调用。"""

import logging

from app.rag.client.embedding_client import embedding_client
from app.rag.models.chunk_hit import ChunkHit
from app.rag.retrieval.pgvector_store import pgvector_store

logger = logging.getLogger(__name__)


class RetrieverService:
    """query → embed → pgvector TopK → score 阈值过滤。"""

    def __init__(self) -> None:
        self._embedder = embedding_client
        self._store = pgvector_store

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        score_threshold: float = 0.7,
        team_id: int | None = None,
    ) -> list[ChunkHit]:
        if team_id is None:
            logger.warning("retrieve 缺少 team_id，返回空结果以防越权")
            return []

        query_vec = await self._embedder.embed_query(query)
        rows = await self._store.similarity_search(
            query_vec,
            top_k=top_k,
            team_id=team_id,
        )
        filtered = [h for h in rows if h.score >= score_threshold]
        logger.info(
            "rag retrieve team_id=%s hits=%d filtered=%d",
            team_id,
            len(rows),
            len(filtered),
        )
        return filtered


retriever_service = RetrieverService()
