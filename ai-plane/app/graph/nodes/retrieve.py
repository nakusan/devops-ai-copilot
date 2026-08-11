"""RetrieveNode — 调用 RAG Retriever，写入 retrieved_chunks / citations。"""

import logging
import time
from typing import Any

from app.graph.state import DiagnosisState
from app.observability.logging import chat_msg, preview
from app.observability.metrics import RAG_RETRIEVAL_LATENCY
from app.observability.otel import get_tracer
from app.rag.retrieval.retriever import retriever_service

logger = logging.getLogger(__name__)
_tracer = get_tracer("ai-plane.rag")


async def retrieve_node(state: DiagnosisState) -> dict[str, Any]:
    """pgvector 检索，按 team_id 过滤（6.4 §3.6）。"""
    cfg = state.get("agent_config") or {}
    if not cfg.get("enable_rag", True):
        logger.info(
            chat_msg("11.retrieve", "skipped=true reason=enable_rag_false"),
            extra={"trace_id": state.get("trace_id") or ""},
        )
        return {"retrieved_chunks": [], "citations": []}

    team_id = state.get("user_context", {}).get("team_id")
    query = state.get("user_message", "")
    top_k = int(cfg.get("rag_top_k", 5))
    threshold = float(cfg.get("rag_score_threshold", 0.7))
    started = time.perf_counter()
    with _tracer.start_as_current_span("rag.retrieve") as span:
        hits = await retriever_service.retrieve(
            query=query,
            top_k=top_k,
            score_threshold=threshold,
            team_id=team_id,
        )
        span.set_attribute("rag.hits", len(hits))
        RAG_RETRIEVAL_LATENCY.observe(time.perf_counter() - started)

    chunks = [h.to_retrieved_dict() for h in hits]
    citations = [h.to_citation() for h in hits]
    titles = [str(c.get("docTitle") or c.get("chunkId") or "") for c in citations[:5]]
    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        chat_msg(
            "11.retrieve",
            f"teamId={team_id} topK={top_k} threshold={threshold} "
            f"hits={len(hits)} latencyMs={latency_ms} "
            f"titles={titles} query=\"{preview(query)}\"",
        ),
        extra={"trace_id": state.get("trace_id") or ""},
    )
    return {"retrieved_chunks": chunks, "citations": citations}
