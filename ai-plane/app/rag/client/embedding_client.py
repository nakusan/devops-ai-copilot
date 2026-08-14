"""OpenAI 兼容 Embedding 客户端。"""

import hashlib
import math
import struct
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from app.config import settings
from app.observability.otel import get_tracer

if TYPE_CHECKING:
    pass

_tracer = get_tracer("ai-plane.rag")


def deterministic_embed(text: str, dim: int | None = None) -> list[float]:
    """无 API Key 时的确定性假向量（dev/CI 用）。

    同一文本始终得到同一向量，便于 seed 数据与单元测试对齐。
    TODO(Phase-3/W7): hash 假向量 fallback — 无 Embedding Key 时保证 dev/CI 可跑
    — 配置 EMBEDDING_API_KEY 后自动切真 embed API
    """
    dimension = dim or settings.embedding_dim
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        block = hashlib.sha256(digest + struct.pack(">I", counter)).digest()
        counter += 1
        for i in range(0, len(block), 4):
            if len(values) >= dimension:
                break
            chunk = block[i : i + 4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\0")
            raw = struct.unpack(">I", chunk)[0]
            # 映射到 [-1, 1]
            values.append((raw / 0xFFFFFFFF) * 2 - 1)
    # L2 归一化，与余弦距离检索一致
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class EmbeddingClient:
    """query / batch embed；有 Key 走 API，否则 hash 降级。"""

    def __init__(self) -> None:
        self._model = settings.embedding_model
        self._dim = settings.embedding_dim
        api_key = settings.effective_embedding_api_key()
        base_url = settings.embedding_base_url or settings.llm_base_url
        self._client: AsyncOpenAI | None = None
        if api_key and base_url:
            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with _tracer.start_as_current_span("rag.embed") as span:
            span.set_attribute("rag.embed.batch_size", len(texts))
            span.set_attribute("rag.embed.model", self._model)
            if self._client is None:
                span.set_attribute("rag.embed.mode", "deterministic")
                return [deterministic_embed(t, self._dim) for t in texts]
            span.set_attribute("rag.embed.mode", "api")
            resp = await self._client.embeddings.create(model=self._model, input=texts)
            vectors = [item.embedding for item in resp.data]
            for vec in vectors:
                if len(vec) != self._dim:
                    raise ValueError(
                        f"embedding dim mismatch: got {len(vec)} expected {self._dim} "
                        f"(model={self._model}); 请核对 EMBEDDING_DIM 与 DB vector(N)"
                    )
            return vectors

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_batch([query])
        return vectors[0]


# 进程内单例
embedding_client = EmbeddingClient()
