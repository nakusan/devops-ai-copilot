"""在线检索入口 — 供 Agent retrieve_knowledge 调用。"""

import logging
import time

from app.config import settings
from app.observability.logging import chat_msg, preview
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
        score_threshold: float | None = None,
        team_id: int | None = None,
    ) -> list[ChunkHit]:
        if team_id is None:
            logger.warning("retrieve 缺少 team_id，返回空结果以防越权")
            return []

        threshold = settings.effective_rag_score_threshold(score_threshold)
        started = time.perf_counter()
        query_vec = await self._embedder.embed_query(query)
        rows = await self._store.similarity_search(
            query_vec,
            top_k=top_k,
            team_id=team_id,
        )
        filtered = [h for h in rows if h.score >= threshold]

        top_score = round(rows[0].score, 4) if rows else 0.0
        message = chat_msg(
            "12.检索",
            f"query=\"{preview(query)}\" hits={len(filtered)}/{len(rows)} "
            f"threshold={threshold:.2f} topScore={top_score} "
            f"latencyMs={int((time.perf_counter() - started) * 1000)}",
        )
        if rows and not filtered:
            # 捞到了内容但一条都没过阈值：附带原始分数便于调 threshold
            logger.warning(
                "%s reason=all_below_threshold scores=%s",
                message,
                [round(h.score, 4) for h in rows],
            )
        elif filtered:
            logger.info(message)
        return filtered


retriever_service = RetrieverService()
