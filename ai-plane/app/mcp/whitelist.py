"""Tool 白名单与参数校验（设计 6.6 §3.5）— 禁止任意 tool / 注入。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

WHITELIST: dict[str, set[str]] = {
    "prometheus": {"prometheus_query", "prometheus_query_range"},
    "postgres-readonly": {"readonly_sql"},
}

ALLOWED_PROM_QUERIES = {
    "db_connections",
    "service_p99_latency",
    "jvm_heap_used",
    "cpu_usage_percent",
    "http_qps",
}


class ToolNotAllowedError(ValueError):
    """非白名单 tool。"""


class PromQueryArgs(BaseModel):
    query: str = Field(max_length=256)

    @field_validator("query")
    @classmethod
    def only_enum_keys(cls, v: str) -> str:
        # MVP：只允许枚举 key，Server 内部映射；禁止用户/LLM 自由 PromQL
        if v not in ALLOWED_PROM_QUERIES:
            raise ValueError(f"query not allowed: {v}")
        return v


class ReadonlySqlArgs(BaseModel):
    sql: str = Field(max_length=512)

    @field_validator("sql")
    @classmethod
    def select_only(cls, v: str) -> str:
        normalized = v.strip().lower()
        if not normalized.startswith("select"):
            raise ValueError("only SELECT allowed")
        forbidden = ("insert", "update", "delete", "drop", "alter", "truncate", ";")
        if any(kw in normalized for kw in forbidden):
            raise ValueError("forbidden keyword in sql")
        return v


def ensure_allowed(server: str, tool: str) -> None:
    allowed = WHITELIST.get(server)
    if allowed is None or tool not in allowed:
        raise ToolNotAllowedError(f"{server}/{tool}")


def validate_arguments(server: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    ensure_allowed(server, tool)
    if server == "prometheus" and tool in {"prometheus_query", "prometheus_query_range"}:
        return PromQueryArgs.model_validate(arguments).model_dump()
    if server == "postgres-readonly" and tool == "readonly_sql":
        return ReadonlySqlArgs.model_validate(arguments).model_dump()
    raise ToolNotAllowedError(f"{server}/{tool}")
