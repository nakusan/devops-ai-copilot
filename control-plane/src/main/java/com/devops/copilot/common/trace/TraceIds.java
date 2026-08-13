package com.devops.copilot.common.trace;

import org.slf4j.MDC;

/**
 * TraceId / SpanId 访问入口。Filter / micrometer-tracing 负责写入 MDC；
 * 业务与异常处理只读此处，避免散落魔法字符串（设计 6.10 §6.5）。
 *
 * <p>MDC key 与 micrometer-tracing 默认一致（{@code traceId} / {@code spanId}）。
 */
public final class TraceIds {

    public static final String MDC_KEY = "traceId";
    public static final String MDC_SPAN_KEY = "spanId";
    public static final String HEADER_X_TRACE_ID = "X-Trace-Id";
    public static final String HEADER_TRACEPARENT = "traceparent";

    private TraceIds() {
    }

    public static String current() {
        String id = MDC.get(MDC_KEY);
        return id == null ? "" : id;
    }

    public static String currentSpanId() {
        String id = MDC.get(MDC_SPAN_KEY);
        return id == null ? "" : id;
    }

    public static void set(String traceId) {
        MDC.put(MDC_KEY, traceId);
    }

    public static void setSpanId(String spanId) {
        MDC.put(MDC_SPAN_KEY, spanId);
    }

    public static void clear() {
        MDC.remove(MDC_KEY);
        MDC.remove(MDC_SPAN_KEY);
    }
}
