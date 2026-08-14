"""RetrieveNode — 调用 RAG Retriever，写入 retrieved_chunks / citations。

日志由 RetrieverService 统一打印（step=12.检索）：只有它同时掌握
被阈值淘汰的原始分数与最终命中，在此再打一条只会重复。
"""

import logging
import time
from typing import Any

from app.config import settings
from app.graph.state import DiagnosisState
from app.observability.metrics import RAG_RETRIEVAL_LATENCY, observe_with_exemplar
from app.observability.otel import get_tracer
from app.rag.retrieval.retriever import retriever_service

logger = logging.getLogger(__name__)
_tracer = get_tracer("ai-plane.rag")


async def retrieve_node(state: DiagnosisState) -> dict[str, Any]:
    """pgvector 检索，按 team_id 过滤（6.4 §3.6）。"""
    cfg = state.get("agent_config") or {}
    if not cfg.get("enable_rag", True):
        return {"retrieved_chunks": [], "citations": []}

    team_id = state.get("user_context", {}).get("team_id")
    query = state.get("user_message", "")
    top_k = int(cfg.get("rag_top_k", 5))
    threshold = settings.effective_rag_score_threshold(cfg.get("rag_score_threshold"))
    started = time.perf_counter()
    with _tracer.start_as_current_span("rag.retrieve") as span:
        hits = await retriever_service.retrieve(
            query=query,
            top_k=top_k,
            score_threshold=threshold,
            team_id=team_id,
        )
        span.set_attribute("rag.hits", len(hits))
        observe_with_exemplar(RAG_RETRIEVAL_LATENCY, time.perf_counter() - started)

    return {
        "retrieved_chunks": [h.to_retrieved_dict() for h in hits],
        "citations": [h.to_citation() for h in hits],
    }
