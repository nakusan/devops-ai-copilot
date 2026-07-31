"""切块载荷（写入 Java chunks/batch）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    chunk_index: int
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkPayload(BaseModel):
    chunk_index: int
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "chunkIndex": self.chunk_index,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
        }
