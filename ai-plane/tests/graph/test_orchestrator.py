"""DiagnosisOrchestrator 集成测试（Mock LLM + Mock Retriever）。"""

import asyncio
import json
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.graph.models.internal_chat_request import (
    AgentConfig,
    InternalChatRequest,
    UserContext,
)
from app.graph.orchestrator import run_diagnosis_stream
from app.rag.models.chunk_hit import ChunkHit


def _req(user_message: str, *, enable_rag: bool = True) -> InternalChatRequest:
    return InternalChatRequest(
        traceId="t1",
        sessionId="11111111-1111-1111-1111-111111111111",
        userMessage=user_message,
        history=[],
        agentConfig=AgentConfig(
            model="deepseek-chat",
            systemPrompt="test",
            enableRag=enable_rag,
            enableMcp=True,
            ragTopK=5,
            ragScoreThreshold=0.7,
            temperature=0.2,
        ),
        userContext=UserContext(userId=1, teamId=1),
    )


async def _collect_events(req: InternalChatRequest) -> list[dict]:
    cancel = asyncio.Event()
    events = []
    with patch(
        "app.graph.nodes.retrieve.retriever_service.retrieve",
        new=AsyncMock(
            return_value=[
                ChunkHit(
                    chunk_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                    document_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                    document_title="STATUS_CODE.md",
                    content="STATUS_899: 支付渠道超时",
                    score=0.91,
                )
            ]
        ),
    ):
        async for evt in run_diagnosis_stream(req, cancel):
            events.append(json.loads(evt.model_dump_json(exclude_none=True)))
    return events


@pytest.mark.asyncio
async def test_orchestrator_rag_path_emits_citation_and_done() -> None:
    events = await _collect_events(_req("STATUS_899 是什么原因？"))
    types = [e["type"] for e in events]
    assert "token" in types
    assert "citation" in types
    assert types[-1] == "done"
    done = events[-1]["done"]
    assert done["intent"] == "rag"
    assert len(done["citations"]) >= 1
    assert "usage" in done


@pytest.mark.asyncio
async def test_orchestrator_tool_path_has_tool_calls() -> None:
    events = await _collect_events(_req("当前连接数正常吗？"))
    done = events[-1]["done"]
    assert done["intent"] == "tool"
    assert len(done["toolCalls"]) >= 1
    # W11：经 MCP Mock，结果应含 85
    payload = done["toolCalls"][0]
    result = payload.get("result") or {}
    assert result.get("db_connections") == 85 or result.get("value") == 85


@pytest.mark.asyncio
async def test_orchestrator_rag_and_tool_parallel() -> None:
    events = await _collect_events(_req("STATUS_899 是什么？连接数正常吗？"))
    done = events[-1]["done"]
    assert done["intent"] == "rag_and_tool"
    assert len(done["citations"]) >= 1
    assert len(done["toolCalls"]) >= 1
