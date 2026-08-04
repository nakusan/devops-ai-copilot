package com.devops.copilot.common.trace;

import org.slf4j.MDC;

import java.util.concurrent.ThreadLocalRandom;

/**
 * TraceId / SpanId 访问入口。Filter 负责写入 MDC；业务与异常处理只读此处，避免散落魔法字符串。
 *
 * <p>MVP 未挂完整 OTel Agent 时，spanId 由本类生成 16 位 hex，供出站 traceparent 与日志关联（设计 6.7）。
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

    /** 生成 W3C 兼容的 16 位 hex span-id。 */
    public static String newSpanId() {
        long n = ThreadLocalRandom.current().nextLong();
        // span-id 不能全 0
        if (n == 0L) {
            n = 1L;
        }
        return String.format("%016x", n);
    }

    public static void clear() {
        MDC.remove(MDC_KEY);
        MDC.remove(MDC_SPAN_KEY);
    }
}
