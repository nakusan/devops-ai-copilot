"""pgvector 只读检索 — team 过滤 + embedding 版本过滤。"""

import logging

import asyncpg

from app.config import settings
from app.rag.models.chunk_hit import ChunkHit

logger = logging.getLogger(__name__)

# 6.4 设计：余弦距离 <=>，score = 1 - distance
_SIMILARITY_SQL = """
SELECT
    c.id AS chunk_id,
    c.document_id,
    c.content,
    c.metadata_json,
    d.title AS document_title,
    1 - (c.embedding <=> $1::vector) AS score
FROM knowledge_chunks c
JOIN knowledge_documents d ON d.id = c.document_id
WHERE d.status = 'COMPLETED'
  AND d.team_id = $2
  AND ($3::text IS NULL OR c.metadata_json->>'embedding_model_version' = $3)
ORDER BY c.embedding <=> $1::vector
LIMIT $4
"""


def _vector_to_pg_literal(values: list[float]) -> str:
    """asyncpg 接受 '[...]'::vector 字符串形式。"""
    inner = ",".join(f"{v:.8f}" for v in values)
    return f"[{inner}]"


class PgVectorStore:
    """PostgreSQL + pgvector 相似度搜索（只读连接）。"""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or settings.database_readonly_url
        self._pool: asyncpg.Pool | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._dsn)

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            if not self._dsn:
                raise RuntimeError("DATABASE_READONLY_URL 未配置")
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=4)
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def similarity_search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        team_id: int,
        embedding_model_version: str | None = None,
    ) -> list[ChunkHit]:
        if not self.is_configured:
            logger.warning("pgvector 未配置 DATABASE_READONLY_URL，跳过检索")
            return []

        pool = await self._get_pool()
        vec_literal = _vector_to_pg_literal(query_vector)
        version = embedding_model_version or settings.embedding_model_version

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                _SIMILARITY_SQL,
                vec_literal,
                team_id,
                version,
                top_k,
            )

        hits: list[ChunkHit] = []
        for row in rows:
            hits.append(
                ChunkHit(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    document_title=row["document_title"],
                    content=row["content"],
                    score=float(row["score"]),
                    metadata=dict(row["metadata_json"] or {}),
                )
            )
        return hits


pgvector_store = PgVectorStore()
