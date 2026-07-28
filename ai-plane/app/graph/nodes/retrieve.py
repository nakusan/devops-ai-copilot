"""RetrieveNode — 调用 RAG Retriever，写入 retrieved_chunks / citations。"""

from typing import Any

from app.graph.state import DiagnosisState
from app.rag.retrieval.retriever import retriever_service


async def retrieve_node(state: DiagnosisState) -> dict[str, Any]:
    """pgvector 检索，按 team_id 过滤（6.4 §3.6）。"""
    cfg = state.get("agent_config") or {}
    if not cfg.get("enable_rag", True):
        return {"retrieved_chunks": [], "citations": []}

    team_id = state.get("user_context", {}).get("team_id")
    hits = await retriever_service.retrieve(
        query=state["user_message"],
        top_k=int(cfg.get("rag_top_k", 5)),
        score_threshold=float(cfg.get("rag_score_threshold", 0.7)),
        team_id=team_id,
    )

    chunks = [h.to_retrieved_dict() for h in hits]
    citations = [h.to_citation() for h in hits]
    return {"retrieved_chunks": chunks, "citations": citations}
