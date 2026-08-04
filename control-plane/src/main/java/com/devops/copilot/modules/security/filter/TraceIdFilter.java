package com.devops.copilot.modules.security.filter;

import com.devops.copilot.common.trace.TraceIds;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Optional;
import java.util.UUID;

/**
 * 全链路 TraceId 注入（原则 P9：以 W3C traceparent 为准）。
 *
 * <p>为何放在 Security 链之前：401/429 响应也要带同一个 traceId，方便客户端报障。
 *
 * <p>MVP 同步写入 spanId 到 MDC，供 JSON 日志与出站 traceparent 使用（完整 OTel SDK 埋点可 V1 替换）。
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TraceIdFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        try {
            ParsedTrace parsed = parseTraceparent(request.getHeader(TraceIds.HEADER_TRACEPARENT))
                    .orElseGet(() -> new ParsedTrace(
                            UUID.randomUUID().toString().replace("-", ""),
                            TraceIds.newSpanId()));
            TraceIds.set(parsed.traceId());
            TraceIds.setSpanId(parsed.spanId());
            response.setHeader(TraceIds.HEADER_X_TRACE_ID, parsed.traceId());
            filterChain.doFilter(request, response);
        } finally {
            // 线程可能被容器复用，必须清理 MDC，否则串请求
            TraceIds.clear();
        }
    }

    /**
     * traceparent 格式：version-traceId-spanId-flags，例如
     * {@code 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01}
     */
    static Optional<String> extractFromTraceparent(String traceparent) {
        return parseTraceparent(traceparent).map(ParsedTrace::traceId);
    }

    static Optional<ParsedTrace> parseTraceparent(String traceparent) {
        if (traceparent == null || traceparent.isBlank()) {
            return Optional.empty();
        }
        String[] parts = traceparent.trim().split("-");
        if (parts.length < 4) {
            return Optional.empty();
        }
        String traceId = parts[1];
        String parentSpanId = parts[2];
        if (traceId.length() != 32 || parentSpanId.length() != 16) {
            return Optional.empty();
        }
        // 入站 parent 作为关联参考；本服务作为新 span 根，生成自己的 spanId
        return Optional.of(new ParsedTrace(traceId, TraceIds.newSpanId()));
    }

    record ParsedTrace(String traceId, String spanId) {
    }
}
