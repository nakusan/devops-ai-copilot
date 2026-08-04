"""Prometheus 业务指标定义（设计 6.7 §3.4.3 / §3.5.2）。"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# 桶覆盖聊天（含 LLM）常见延迟区间
_CHAT_BUCKETS = (0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0)
_RAG_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
_MCP_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
_LLM_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
_INGEST_BUCKETS = (1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0)

CHAT_STREAM_DURATION = Histogram(
    "chat_stream_duration_seconds",
    "AI plane chat stream duration",
    buckets=_CHAT_BUCKETS,
)

RAG_RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_latency_seconds",
    "RAG retrieval latency",
    buckets=_RAG_BUCKETS,
)

MCP_TOOL_LATENCY = Histogram(
    "mcp_tool_latency_seconds",
    "MCP tool call latency",
    ["server", "tool"],
    buckets=_MCP_BUCKETS,
)

MCP_TOOL_CALLS = Counter(
    "mcp_tool_calls_total",
    "MCP tool calls",
    ["server", "tool", "status"],
)

LLM_TTFB = Histogram(
    "llm_time_to_first_token_seconds",
    "LLM time to first token",
    buckets=_LLM_BUCKETS,
)

INGEST_DURATION = Histogram(
    "rag_ingest_duration_seconds",
    "Knowledge ingest job duration",
    buckets=_INGEST_BUCKETS,
)

INGEST_FAILURES = Counter(
    "rag_ingest_failures_total",
    "Knowledge ingest failures",
    ["reason"],
)

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled by AI plane",
    ["method", "path", "status"],
)
