"""OpenAI 兼容 tools schema；按 Agent 开关裁剪。"""

from __future__ import annotations

from typing import Any

from app.mcp.config import get_active_servers
from app.mcp.whitelist import ALLOWED_PROM_QUERIES

# 工具名 → 所属能力，供 done.intent 推导
TOOL_KIND: dict[str, str] = {
    "retrieve_knowledge": "rag",
    "prometheus_query": "mcp",
    "readonly_sql": "mcp",
    "list_analysis_jobs": "analysis",
    "get_analysis_job": "analysis",
}


def build_openai_tools(agent_config: dict[str, Any] | None) -> list[dict[str, Any]]:
    """按 enable_rag / enable_mcp / 活跃 MCP server 生成 function tools。"""
    cfg = agent_config or {}
    tools: list[dict[str, Any]] = []

    if cfg.get("enable_rag", True):
        tools.append(
            _fn(
                "retrieve_knowledge",
                "从团队知识库检索运维文档、错误码说明、故障手册。"
                "问候、闲聊、纯确认不要调用。query 应改写成适合检索的短语。",
                {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "检索用查询词，可改写用户原话",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回条数，默认用 Agent 配置",
                            "minimum": 1,
                            "maximum": 20,
                        },
                    },
                    "required": ["query"],
                },
            )
        )

    if cfg.get("enable_mcp", True):
        servers = set(get_active_servers(cfg))
        if "prometheus" in servers:
            enum_keys = sorted(ALLOWED_PROM_QUERIES)
            tools.append(
                _fn(
                    "prometheus_query",
                    "查询瞬时监控指标（枚举 key，禁止自由 PromQL）。"
                    f"可用 key: {', '.join(enum_keys)}",
                    {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "enum": enum_keys,
                                "description": "指标枚举 key",
                            },
                        },
                        "required": ["query"],
                    },
                )
            )
        if "postgres-readonly" in servers:
            tools.append(
                _fn(
                    "readonly_sql",
                    "对只读库执行单条 SELECT（禁止写操作与多语句）。",
                    {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "以 SELECT 开头的 SQL",
                            },
                        },
                        "required": ["sql"],
                    },
                )
            )

    # 分析任务查询不依赖 enable_mcp；始终提供，便于「刚才那个 heap」
    tools.append(
        _fn(
            "list_analysis_jobs",
            "列出当前用户最近的大文件分析任务（含 jobId/fileType/status）。"
            "不确定要看哪一次时先 list 再 get。",
            {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "条数，默认 5，最大 20",
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": [],
            },
        )
    )
    tools.append(
        _fn(
            "get_analysis_job",
            "获取指定分析任务详情与结果摘要。"
            "省略 job_id 时返回该用户最近一次已完成（COMPLETED）任务。",
            {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "分析任务 UUID；可选",
                    },
                },
                "required": [],
            },
        )
    )
    return tools


def derive_intent(used_tool_names: set[str]) -> str:
    """由实际调用过的工具推导 done.intent，兼容既有 metadata。"""
    kinds = {TOOL_KIND.get(n) for n in used_tool_names if n in TOOL_KIND}
    kinds.discard(None)
    has_rag = "rag" in kinds
    has_mcp = "mcp" in kinds
    has_analysis = "analysis" in kinds
    if has_analysis and not has_rag and not has_mcp:
        return "analysis"
    if has_analysis:
        # 分析 + 其它能力：仍标 analysis，便于前端识别文件诊断路径
        return "analysis"
    if has_rag and has_mcp:
        return "rag_and_tool"
    if has_rag:
        return "rag"
    if has_mcp:
        return "tool"
    return "direct"


def _fn(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }
