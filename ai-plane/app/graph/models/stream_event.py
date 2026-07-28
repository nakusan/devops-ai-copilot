"""NDJSON 行级流事件（Python → Java）。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class StreamEvent(BaseModel):
    """对内流式协议：每行一个 JSON。

    type:
      - token: LLM/Mock 增量文本
      - citation: 检索引用（本阶段 Mock 可不发）
      - done: 正常结束，含 usage 等
      - error: 失败
    """

    type: Literal["token", "citation", "done", "error"]
    text: str | None = None
    data: dict[str, Any] | None = None
    done: dict[str, Any] | None = None
    error: dict[str, Any] | None = Field(default=None)


def token_event(text: str) -> StreamEvent:
    return StreamEvent(type="token", text=text)


def done_event(done: dict[str, Any]) -> StreamEvent:
    return StreamEvent(type="done", done=done)


def error_event(code: str, message: str) -> StreamEvent:
    return StreamEvent(type="error", error={"code": code, "message": message})


def citation_event_from_list(citations: list[dict[str, Any]]) -> StreamEvent:
    return StreamEvent(type="citation", data={"citations": citations})
