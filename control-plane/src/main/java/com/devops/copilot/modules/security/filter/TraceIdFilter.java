package com.devops.copilot.modules.security.filter;

import com.devops.copilot.common.trace.TraceIds;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/**
 * 将当前 Micrometer span 的 traceId 写入响应头 {@code X-Trace-Id}（设计 6.10 §6.4）。
 *
 * <p>traceId 的生成 / W3C 传播由 micrometer-tracing + ServerHttpObservationFilter 负责。
 * 本 Filter 挂在 Security 链最前（见 {@code SecurityConfig}），晚于 Servlet 层的
 * ObservationFilter，因此 {@link Tracer#currentSpan()} 通常可用；401/429 仍带同一 traceId。
 *
 * <p>{@code @Order(HIGHEST_PRECEDENCE + 2)} 与设计书一致；因 {@code FilterRegistrationConfig}
 * 禁用了 Servlet 自动注册，实际顺序由 Security 链决定，已天然晚于 ObservationFilter。
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 2)
public class TraceIdFilter extends OncePerRequestFilter {

    private final Tracer tracer;

    public TraceIdFilter(Tracer tracer) {
        this.tracer = tracer;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        try {
            Span current = tracer.currentSpan();
            String traceId = current != null ? current.context().traceId() : fallbackTraceId();
            TraceIds.set(traceId);
            if (current != null) {
                TraceIds.setSpanId(current.context().spanId());
            }
            response.setHeader(TraceIds.HEADER_X_TRACE_ID, traceId);
            filterChain.doFilter(request, response);
        } finally {
            // 线程可能被容器复用，必须清理 MDC，否则串请求
            TraceIds.clear();
        }
    }

    /** tracing 关闭或 Observation 尚未创建时的降级路径（设计 6.10 §11）。 */
    static String fallbackTraceId() {
        return UUID.randomUUID().toString().replace("-", "");
    }
}
