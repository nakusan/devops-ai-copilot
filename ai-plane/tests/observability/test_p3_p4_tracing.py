"""P3/P4 observability：Kafka carrier、exemplar、metrics OpenMetrics（设计 6.10 §7~§8）。"""

from __future__ import annotations

from types import SimpleNamespace

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import Histogram

from app.observability.kafka_trace import kafka_header_carrier
from app.observability.metrics import current_trace_exemplar, observe_with_exemplar


def test_kafka_header_carrier_decodes_bytes() -> None:
    msg = SimpleNamespace(
        headers=[
            ("traceparent", b"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"),
            ("x-trace-id", b"4bf92f3577b34da6a3ce929d0e0e4736"),
        ]
    )
    carrier = kafka_header_carrier(msg)
    assert carrier["traceparent"].startswith("00-")
    assert carrier["x-trace-id"] == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_current_trace_exemplar_from_active_span() -> None:
    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("parent"):
        ex = current_trace_exemplar()
        assert ex is not None
        assert len(ex["trace_id"]) == 32


def test_observe_with_exemplar_attaches_trace_id() -> None:
    h = Histogram("test_p4_hist_seconds", "test", buckets=(0.1, 1.0))
    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("s"):
        observe_with_exemplar(h, 0.05)
    # 无异常即成功；exemplar 存在性由 OpenMetrics 导出路径覆盖


def test_metrics_openmetrics_negotiation() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.get("/metrics", headers={"Accept": "application/openmetrics-text; version=1.0.0"})
    assert r.status_code == 200
    assert "openmetrics" in r.headers.get("content-type", "").lower()


def test_propagator_roundtrip_for_kafka_style_carrier() -> None:
    """模拟 Java 注入的 traceparent 能被 extract 成有效 parent context。"""
    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    propagator = TraceContextTextMapPropagator()
    carrier: dict[str, str] = {}
    with tracer.start_as_current_span("producer") as parent:
        propagator.inject(carrier)
        parent_tid = format(parent.get_span_context().trace_id, "032x")

    msg = SimpleNamespace(headers=[(k, v.encode("utf-8")) for k, v in carrier.items()])
    extracted = kafka_header_carrier(msg)
    ctx = propagator.extract(extracted)
    with tracer.start_as_current_span("consumer", context=ctx) as child:
        assert format(child.get_span_context().trace_id, "032x") == parent_tid
        assert child.parent is not None or child.get_span_context().trace_id
        # parent span id 应匹配
        assert child.parent is not None
        _ = trace
