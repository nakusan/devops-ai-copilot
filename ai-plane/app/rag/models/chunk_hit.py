"""检索命中结果 — 供 RetrieveNode / SynthesizeNode / citation 使用。"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChunkHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_retrieved_dict(self) -> dict[str, Any]:
        """写入 DiagnosisState.retrieved_chunks 的序列化格式。"""
        return {
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "document_title": self.document_title,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }

    def to_citation(self) -> dict[str, Any]:
        """done 事件 citations 载荷（camelCase 对齐 Java metadata）。"""
        return {
            "chunkId": str(self.chunk_id),
            "documentTitle": self.document_title,
            "score": self.score,
        }
