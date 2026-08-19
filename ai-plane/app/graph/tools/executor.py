"""执行 LLM 给出的 tool_calls：RAG / MCP / 分析任务。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.clients.java_internal_client import java_internal_client
from app.config import settings
from app.mcp.client import mcp_client
from app.rag.retrieval.retriever import retriever_service

logger = logging.getLogger(__name__)


@dataclass
class ToolExecution:
    """单次工具执行结果，供 orchestrator 写回 messages / 发 SSE。"""

    tool_call_id: str
    name: str
    arguments: dict[str, Any]
    success: bool
    content: str
    # 供 done.toolCalls / citation
    result: Any = None
    error: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    # 写入 done.toolCalls 的结构化记录
    tool_call_record: dict[str, Any] = field(default_factory=dict)


async def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    agent_config: dict[str, Any],
    user_context: dict[str, Any],
    trace_id: str | None = None,
) -> list[ToolExecution]:
    """并行执行同一轮 tool_calls。"""
    if not tool_calls:
        return []
    return list(
        await asyncio.gather(
            *[
                _execute_one(
                    tc,
                    agent_config=agent_config,
                    user_context=user_context,
                    trace_id=trace_id,
                )
                for tc in tool_calls
            ]
        )
    )


async def _execute_one(
    tc: dict[str, Any],
    *,
    agent_config: dict[str, Any],
    user_context: dict[str, Any],
    trace_id: str | None,
) -> ToolExecution:
    name = str(tc.get("name") or "")
    call_id = str(tc.get("id") or name)
    raw_args = tc.get("arguments") or {}
    if isinstance(raw_args, str):
        try:
            arguments = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            return _fail(call_id, name, {}, "INVALID_ARGS", "arguments 不是合法 JSON")
    elif isinstance(raw_args, dict):
        arguments = raw_args
    else:
        return _fail(call_id, name, {}, "INVALID_ARGS", "arguments 类型错误")

    try:
        if name == "retrieve_knowledge":
            return await _retrieve(call_id, name, arguments, agent_config, user_context)
        if name == "prometheus_query":
            return await _mcp(
                call_id, name, "prometheus", "prometheus_query", arguments, trace_id
            )
        if name == "readonly_sql":
            return await _mcp(
                call_id, name, "postgres-readonly", "readonly_sql", arguments, trace_id
            )
        if name == "list_analysis_jobs":
            return await _list_analysis(call_id, name, arguments, user_context)
        if name == "get_analysis_job":
            return await _get_analysis(call_id, name, arguments, user_context)
        return _fail(call_id, name, arguments, "UNKNOWN_TOOL", f"未知工具: {name}")
    except Exception as ex:  # noqa: BLE001
        logger.exception("tool_exec_failed name=%s", name, extra={"trace_id": trace_id or ""})
        return _fail(call_id, name, arguments, "TOOL_ERROR", str(ex)[:300])


async def _retrieve(
    call_id: str,
    name: str,
    arguments: dict[str, Any],
    agent_config: dict[str, Any],
    user_context: dict[str, Any],
) -> ToolExecution:
    if not agent_config.get("enable_rag", True):
        return _fail(call_id, name, arguments, "RAG_DISABLED", "RAG 已关闭")
    query = str(arguments.get("query") or "").strip()
    if not query:
        return _fail(call_id, name, arguments, "INVALID_ARGS", "query 不能为空")
    top_k = int(arguments.get("top_k") or agent_config.get("rag_top_k") or 5)
    top_k = max(1, min(top_k, 20))
    threshold = settings.effective_rag_score_threshold(agent_config.get("rag_score_threshold"))
    team_id = user_context.get("team_id")
    hits = await retriever_service.retrieve(
        query=query,
        top_k=top_k,
        score_threshold=threshold,
        team_id=team_id,
    )
    citations = [h.to_citation() for h in hits]
    payload = [h.to_retrieved_dict() for h in hits]
    content = _truncate(json.dumps(payload, ensure_ascii=False))
    return ToolExecution(
        tool_call_id=call_id,
        name=name,
        arguments=arguments,
        success=True,
        content=content,
        result=payload,
        citations=citations,
        tool_call_record={
            "tool": name,
            "arguments": arguments,
            "result": {"hits": len(hits)},
            "success": True,
        },
    )


async def _mcp(
    call_id: str,
    name: str,
    server: str,
    mcp_tool: str,
    arguments: dict[str, Any],
    trace_id: str | None,
) -> ToolExecution:
    res = await mcp_client.call_tool(server, mcp_tool, arguments, trace_id=trace_id)
    if not res.success:
        err = res.error or "MCP_ERROR"
        return ToolExecution(
            tool_call_id=call_id,
            name=name,
            arguments=arguments,
            success=False,
            content=_truncate(f"工具失败: {err}"),
            error=err,
            tool_call_record={
                "tool": name,
                "server": server,
                "arguments": arguments,
                "result": {"error": err},
                "success": False,
                "error": err,
            },
        )
    data = res.data if res.data is not None else {}
    content = _truncate(json.dumps(data, ensure_ascii=False))
    return ToolExecution(
        tool_call_id=call_id,
        name=name,
        arguments=arguments,
        success=True,
        content=content,
        result=data,
        tool_call_record={
            "tool": name,
            "server": server,
            "arguments": arguments,
            "result": data,
            "success": True,
        },
    )


async def _list_analysis(
    call_id: str,
    name: str,
    arguments: dict[str, Any],
    user_context: dict[str, Any],
) -> ToolExecution:
    user_id = user_context.get("user_id")
    if user_id is None:
        return _fail(call_id, name, arguments, "MISSING_USER", "缺少 user_id")
    limit = int(arguments.get("limit") or 5)
    jobs = await java_internal_client.list_analysis_jobs(int(user_id), limit=limit)
    content = _truncate(json.dumps(jobs, ensure_ascii=False, default=str))
    return ToolExecution(
        tool_call_id=call_id,
        name=name,
        arguments=arguments,
        success=True,
        content=content,
        result=jobs,
        tool_call_record={
            "tool": name,
            "arguments": arguments,
            "result": {"count": len(jobs)},
            "success": True,
        },
    )


async def _get_analysis(
    call_id: str,
    name: str,
    arguments: dict[str, Any],
    user_context: dict[str, Any],
) -> ToolExecution:
    job_id_raw = arguments.get("job_id") or arguments.get("jobId")
    if job_id_raw:
        try:
            job = await java_internal_client.get_analysis_job(UUID(str(job_id_raw)))
        except Exception as ex:  # noqa: BLE001
            return _fail(call_id, name, arguments, "JOB_FETCH_FAILED", str(ex)[:200])
    else:
        user_id = user_context.get("user_id")
        if user_id is None:
            return _fail(call_id, name, arguments, "MISSING_USER", "缺少 user_id")
        job = await java_internal_client.get_latest_analysis_job(int(user_id))
        if job is None:
            return ToolExecution(
                tool_call_id=call_id,
                name=name,
                arguments=arguments,
                success=True,
                content="暂无已完成的上传分析任务",
                result=None,
                tool_call_record={
                    "tool": name,
                    "arguments": arguments,
                    "result": None,
                    "success": True,
                },
            )
    content = _truncate(json.dumps(job, ensure_ascii=False, default=str))
    return ToolExecution(
        tool_call_id=call_id,
        name=name,
        arguments=arguments,
        success=True,
        content=content,
        result=job,
        tool_call_record={
            "tool": name,
            "arguments": arguments,
            "result": {
                "jobId": job.get("jobId") or job.get("id"),
                "status": job.get("status"),
            },
            "success": True,
        },
    )


def _fail(
    call_id: str,
    name: str,
    arguments: dict[str, Any],
    code: str,
    message: str,
) -> ToolExecution:
    return ToolExecution(
        tool_call_id=call_id,
        name=name,
        arguments=arguments,
        success=False,
        content=_truncate(f"[{code}] {message}"),
        error=f"{code}: {message}",
        tool_call_record={
            "tool": name,
            "arguments": arguments,
            "result": {"error": message, "code": code},
            "success": False,
            "error": f"{code}: {message}",
        },
    )


def _truncate(text: str) -> str:
    limit = max(256, settings.tool_result_max_chars)
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n…(truncated)"
