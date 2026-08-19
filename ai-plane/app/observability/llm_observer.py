"""LLM 调用横切观察器：span / TTFB / usage，与业务解析解耦。

设计意图
--------
llm_client 负责：发请求、解析 choice/chunk、yield token、cancel。
本模块负责：OpenTelemetry span 生命周期、首 token 延迟、usage 属性写入。

用法（非流式规划轮）::

    with LlmObserver.plan(model, temperature).activate() as obs:
        resp = await client.chat.completions.create(...)
        obs.record_usage(parse_openai_usage(resp.usage))
        obs.set_tool_call_count(len(tool_calls))

用法（流式最终轮）::

    with LlmObserver.stream(model, temperature).activate() as obs:
        async for chunk in stream:
            if delta:
                obs.mark_first_token()  # 仅首次生效
                yield token_event(delta)
        obs.finish_with_usage(usage)

用法（本地切片、无 span）::

    obs = LlmObserver.stream(model, temperature)
    obs.begin_clock()
    ...
    obs.mark_first_token()
    obs.finish_with_usage(usage)  # 只 attach usage，无 span 亦可
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.graph.llm.instrumentation import attach_usage, set_usage_span_attrs
from app.observability.metrics import LLM_TTFB, observe_with_exemplar
from app.observability.otel import get_tracer

_tracer = get_tracer("ai-plane.llm")


class LlmObserver:
    """单次 LLM 调用的埋点上下文。

    不持有 OpenAI client，也不解析 tool_calls；只记录可观测性信号。
    """

    def __init__(
        self,
        *,
        span_name: str,
        model: str,
        temperature: float,
        system: str,
    ) -> None:
        self._span_name = span_name
        self._model = model
        self._temperature = temperature
        self._system = system
        self._span: Any | None = None
        self._ttfb_started = 0.0
        self._first_token_seen = False

    # --- 工厂：规划轮 / 流式轮命名统一，避免业务侧拼 span 名 ---

    @classmethod
    def plan(cls, model: str, temperature: float) -> LlmObserver:
        """规划轮（非流式 complete_with_tools）。"""
        return cls(
            span_name="llm.plan",
            model=model,
            temperature=temperature,
            system="openai_compatible",
        )

    @classmethod
    def stream(
        cls,
        model: str,
        temperature: float,
        *,
        system: str = "openai_compatible",
    ) -> LlmObserver:
        """最终回答流式轮（真实 API 或 mock）。"""
        return cls(
            span_name="llm.completion",
            model=model,
            temperature=temperature,
            system=system,
        )

    def begin_clock(self) -> None:
        """启动 TTFB 计时。无 span 的切片路径可单独调用；activate() 内也会调用。"""
        self._ttfb_started = time.perf_counter()
        self._first_token_seen = False

    @contextmanager
    def activate(self) -> Iterator[LlmObserver]:
        """进入 span；退出时自动结束 span（与原先 with start_as_current_span 一致）。

        计时在进入 span 之前启动，对齐原 _openai_stream：
        ``ttfb_started = perf_counter(); with start_as_current_span(...):``
        """
        self.begin_clock()
        with _tracer.start_as_current_span(self._span_name) as span:
            self._span = span
            span.set_attribute("gen_ai.system", self._system)
            span.set_attribute("gen_ai.request.model", self._model)
            span.set_attribute("gen_ai.request.temperature", float(self._temperature))
            try:
                yield self
            finally:
                self._span = None

    def mark_first_token(self) -> None:
        """首个 token / 切片到达时调用；重复调用是空操作。

        对应原逻辑：first_token 标志 + llm.ttfb_ms（有 span 时）+ LLM_TTFB histogram。
        """
        if self._first_token_seen:
            return
        self._first_token_seen = True
        ttfb = time.perf_counter() - self._ttfb_started
        if self._span is not None:
            self._span.set_attribute("llm.ttfb_ms", int(ttfb * 1000))
        observe_with_exemplar(LLM_TTFB, ttfb)

    def record_usage(self, usage: dict[str, Any]) -> None:
        """仅写入 span usage 属性（规划轮：usage 走 LlmTurnResult，不 attach）。"""
        if self._span is not None:
            set_usage_span_attrs(self._span, usage)

    def set_tool_call_count(self, count: int) -> None:
        """规划轮解析出 tool_calls 后打点，便于 Tempo 上区分「调工具 vs 直接答」。"""
        if self._span is not None:
            self._span.set_attribute("llm.tool_calls", int(count))

    def finish_with_usage(self, usage: dict[str, Any]) -> None:
        """流式结束：span usage 属性（若有）+ 模块级暂存（供 pop_stream_usage）。"""
        self.record_usage(usage)
        attach_usage(usage)
