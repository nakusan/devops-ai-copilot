"""批量 Embedding（复用 EmbeddingClient）。"""

from __future__ import annotations

from app.config import settings
from app.rag.client.embedding_client import embedding_client
from app.rag.models.chunk import ChunkPayload, TextChunk


async def embed_chunks(chunks: list[TextChunk]) -> list[ChunkPayload]:
    if not chunks:
        return []
    batch_size = settings.embedding_batch_size
    payloads: list[ChunkPayload] = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vectors = await embedding_client.embed_batch([c.content for c in batch])
        for chunk, vec in zip(batch, vectors, strict=True):
            meta = dict(chunk.metadata)
            meta.setdefault("embedding_model_version", settings.embedding_model_version)
            payloads.append(
                ChunkPayload(
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    embedding=vec,
                    metadata=meta,
                )
            )
    return payloads
