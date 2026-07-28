package com.devops.copilot.common.trace;

import org.slf4j.MDC;

/**
 * TraceId 访问入口。Filter 负责写入 MDC；业务与异常处理只读此处，避免散落魔法字符串。
 */
public final class TraceIds {

    public static final String MDC_KEY = "traceId";
    public static final String HEADER_X_TRACE_ID = "X-Trace-Id";
    public static final String HEADER_TRACEPARENT = "traceparent";

    private TraceIds() {
    }

    public static String current() {
        String id = MDC.get(MDC_KEY);
        return id == null ? "" : id;
    }

    public static void set(String traceId) {
        MDC.put(MDC_KEY, traceId);
    }

    public static void clear() {
        MDC.remove(MDC_KEY);
    }
}
