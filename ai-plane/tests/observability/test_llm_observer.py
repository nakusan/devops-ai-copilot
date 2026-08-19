"""LlmObserver / instrumentation 埋点切片冒烟测试（不调真实 LLM）。"""

from __future__ import annotations

from app.graph.llm.instrumentation import (
    attach_usage,
    merge_usage,
    parse_openai_usage,
    pop_stream_usage,
    prompt_chars,
    set_usage_span_attrs,
)
from app.observability.llm_observer import LlmObserver


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5
    total_tokens = 15


class _FakeSpan:
    def __init__(self) -> None:
        self.attrs: dict = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attrs[key] = value


def test_prompt_chars() -> None:
    assert prompt_chars([{"role": "user", "content": "你好"}]) == 2


def test_parse_openai_usage() -> None:
    assert parse_openai_usage(None) == {}
    assert parse_openai_usage(_FakeUsage()) == {
        "promptTokens": 10,
        "completionTokens": 5,
        "totalTokens": 15,
    }


def test_usage_store_pop() -> None:
    attach_usage({"promptTokens": 1, "completionTokens": 2, "totalTokens": 3})
    assert pop_stream_usage()["totalTokens"] == 3
    assert pop_stream_usage() == {}


def test_merge_usage() -> None:
    total = {"promptTokens": 1, "completionTokens": 1, "totalTokens": 2}
    part = {"promptTokens": 3, "completionTokens": 4, "totalTokens": 7}
    out = merge_usage(total, part)
    assert out == {"promptTokens": 4, "completionTokens": 5, "totalTokens": 9}


def test_set_usage_span_attrs() -> None:
    span = _FakeSpan()
    set_usage_span_attrs(span, {"promptTokens": 2, "completionTokens": 3})
    assert span.attrs["gen_ai.usage.input_tokens"] == 2
    assert span.attrs["gen_ai.usage.output_tokens"] == 3


def test_observer_mark_first_token_idempotent() -> None:
    obs = LlmObserver.stream("m", 0.1)
    obs.begin_clock()
    obs.mark_first_token()
    obs.mark_first_token()  # 第二次应为空操作，不抛错


def test_observer_activate_sets_attrs() -> None:
    with LlmObserver.plan("glm", 0.2).activate() as obs:
        obs.set_tool_call_count(2)
        assert obs._span is not None  # noqa: SLF001 — 冒烟确认 span 已挂上
        obs.record_usage({"promptTokens": 1, "completionTokens": 1})
