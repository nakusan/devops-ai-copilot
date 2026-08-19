"""DiagnosisOrchestrator — ReAct 工具循环集成测试。"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.graph.llm.llm_client import LlmTurnResult
from app.graph.models.internal_chat_request import (
    AgentConfig,
    InternalChatRequest,
    UserContext,
)
from app.graph.models.stream_event import token_event
from app.graph.orchestrator import run_diagnosis_stream
from app.rag.models.chunk_hit import ChunkHit


def _req(
    user_message: str, *, enable_rag: bool = True, enable_mcp: bool = True
) -> InternalChatRequest:
    return InternalChatRequest(
        traceId="t1",
        sessionId="11111111-1111-1111-1111-111111111111",
        userMessage=user_message,
        history=[],
        agentConfig=AgentConfig(
            model="deepseek-chat",
            systemPrompt="test",
            enableRag=enable_rag,
            enableMcp=enable_mcp,
            ragTopK=5,
            temperature=0.2,
            mcpServers=["prometheus"],
        ),
        userContext=UserContext(userId=1, teamId=1),
    )


async def _collect(
    req: InternalChatRequest,
    *,
    plan_side_effect,
    cancel: asyncio.Event | None = None,
) -> list[dict]:
    cancel = cancel or asyncio.Event()
    events: list[dict] = []

    async def _fake_stream(*_a, **_k):
        yield token_event("最终答案")

    with (
        patch(
            "app.graph.orchestrator.complete_with_tools",
            new=AsyncMock(side_effect=plan_side_effect),
        ),
        patch(
            "app.graph.orchestrator.stream_chat",
            new=_fake_stream,
        ),
        patch(
            "app.graph.tools.executor.retriever_service.retrieve",
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
        ),
    ):
        async for evt in run_diagnosis_stream(req, cancel):
            events.append(json.loads(evt.model_dump_json(exclude_none=True)))
    return events


@pytest.mark.asyncio
async def test_direct_no_tools_when_greeting() -> None:
    """规划轮不调工具 → 切片 content → done intent=direct。"""

    async def plan(*_a, **_k):
        return LlmTurnResult(content="你好，有什么可以帮你？", tool_calls=[])

    events = await _collect(_req("你好"), plan_side_effect=plan)
    types = [e["type"] for e in events]
    assert "token" in types
    assert "tool" not in types
    assert types[-1] == "done"
    assert events[-1]["done"]["intent"] == "direct"


@pytest.mark.asyncio
async def test_retrieve_then_answer_emits_citation() -> None:
    calls = {"n": 0}

    async def plan(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return LlmTurnResult(
                content=None,
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "retrieve_knowledge",
                        "arguments": {"query": "STATUS_899"},
                    }
                ],
            )
        return LlmTurnResult(content="STATUS_899 表示支付渠道超时 [1]", tool_calls=[])

    events = await _collect(_req("STATUS_899 是什么原因？"), plan_side_effect=plan)
    types = [e["type"] for e in events]
    assert types.count("tool") >= 2  # start + done
    assert "citation" in types
    assert types[-1] == "done"
    done = events[-1]["done"]
    assert done["intent"] == "rag"
    assert len(done["citations"]) >= 1
    assert any(t.get("tool") == "retrieve_knowledge" for t in done["toolCalls"])


@pytest.mark.asyncio
async def test_prometheus_tool_path() -> None:
    calls = {"n": 0}

    async def plan(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return LlmTurnResult(
                content=None,
                tool_calls=[
                    {
                        "id": "call_p",
                        "name": "prometheus_query",
                        "arguments": {"query": "db_connections"},
                    }
                ],
            )
        return LlmTurnResult(content="当前连接数 85，正常。", tool_calls=[])

    events = await _collect(_req("当前连接数正常吗？"), plan_side_effect=plan)
    done = events[-1]["done"]
    assert done["intent"] == "tool"
    assert len(done["toolCalls"]) >= 1
    payload = done["toolCalls"][0]
    result = payload.get("result") or {}
    assert result.get("db_connections") == 85 or result.get("value") == 85


@pytest.mark.asyncio
async def test_rag_then_tool_multi_round() -> None:
    calls = {"n": 0}

    async def plan(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return LlmTurnResult(
                tool_calls=[
                    {
                        "id": "c1",
                        "name": "retrieve_knowledge",
                        "arguments": {"query": "STATUS_899 阈值"},
                    }
                ],
            )
        if calls["n"] == 2:
            return LlmTurnResult(
                tool_calls=[
                    {
                        "id": "c2",
                        "name": "prometheus_query",
                        "arguments": {"query": "db_connections"},
                    }
                ],
            )
        return LlmTurnResult(content="手册阈值… 当前 85。", tool_calls=[])

    events = await _collect(
        _req("STATUS_899 现在连接数正常吗？"),
        plan_side_effect=plan,
    )
    done = events[-1]["done"]
    assert done["intent"] == "rag_and_tool"
    assert len(done["citations"]) >= 1
    names = {t.get("tool") for t in done["toolCalls"]}
    assert "retrieve_knowledge" in names
    assert "prometheus_query" in names
    # 不应出现「默认乱查」以外的额外 prometheus（这里只有显式一次）
    assert sum(1 for t in done["toolCalls"] if t.get("tool") == "prometheus_query") == 1


@pytest.mark.asyncio
async def test_cancel_before_tools() -> None:
    cancel = asyncio.Event()

    async def plan(*_a, **_k):
        cancel.set()
        return LlmTurnResult(
            tool_calls=[
                {
                    "id": "c1",
                    "name": "prometheus_query",
                    "arguments": {"query": "db_connections"},
                }
            ],
        )

    events = await _collect(_req("查连接数"), plan_side_effect=plan, cancel=cancel)
    assert any(e["type"] == "error" and e["error"]["code"] == "CANCELLED" for e in events)


@pytest.mark.asyncio
async def test_list_analysis_jobs_tool() -> None:
    calls = {"n": 0}

    async def plan(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return LlmTurnResult(
                tool_calls=[
                    {"id": "a1", "name": "list_analysis_jobs", "arguments": {"limit": 3}},
                    {
                        "id": "a2",
                        "name": "get_analysis_job",
                        "arguments": {"job_id": "cccccccc-cccc-cccc-cccc-cccccccccccc"},
                    },
                ],
            )
        return LlmTurnResult(content="heap 分析摘要如下…", tool_calls=[])

    with (
        patch(
            "app.graph.tools.executor.java_internal_client.list_analysis_jobs",
            new=AsyncMock(
                return_value=[
                    {
                        "jobId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "fileType": "HEAP_DUMP",
                        "status": "COMPLETED",
                    }
                ]
            ),
        ),
        patch(
            "app.graph.tools.executor.java_internal_client.get_analysis_job",
            new=AsyncMock(
                return_value={
                    "jobId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    "fileType": "HEAP_DUMP",
                    "status": "COMPLETED",
                    "resultSummary": "leak in Foo",
                }
            ),
        ),
    ):
        events = await _collect(_req("刚才那个 heap"), plan_side_effect=plan)

    done = events[-1]["done"]
    assert done["intent"] == "analysis"
    names = {t.get("tool") for t in done["toolCalls"]}
    assert "list_analysis_jobs" in names
    assert "get_analysis_job" in names
