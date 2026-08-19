"""在线检索入口 — 供 Agent retrieve_knowledge 调用。"""

import logging
import time

from app.config import settings
from app.observability.logging import chat_msg
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

        # scores 覆盖被阈值淘汰的行：只记命中数时，"全被阈值挡掉" 与 "库里没内容"
        # 在日志上完全同形，无法定位。
        message = chat_msg(
            "12.检索",
            f"teamId={team_id} topK={top_k} threshold={threshold:.2f} "
            f"hits={len(filtered)}/{len(rows)} "
            f"latencyMs={int((time.perf_counter() - started) * 1000)} "
            f"scores={[round(h.score, 4) for h in rows]} "
            f"titles={[h.document_title for h in filtered[:3]]}",
        )
        if rows and not filtered:
            # 捞到了内容但一条都没过阈值：阈值大概率高于当前 Embedding 模型的分数区间
            logger.warning("%s reason=all_below_threshold", message)
        else:
            logger.info(message)
        return filtered


retriever_service = RetrieverService()
