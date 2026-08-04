package com.devops.copilot.observability.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

/**
 * 聊天链路业务指标（设计 6.7 §3.3.4）。
 *
 * <p>命名约定：小写 + 点分；Prometheus 导出时 Micrometer 转为下划线
 * （如 {@code chat.requests.total} → {@code chat_requests_total}）。
 */
@Component
public class ChatMetrics {

    private final Counter chatRequests;
    private final Timer chatStreamDuration;
    private final MeterRegistry registry;
    /** 按 error code 缓存 Counter，避免每次 recordError 重复 builder 开销。 */
    private final ConcurrentHashMap<String, Counter> errorCounters = new ConcurrentHashMap<>();

    public ChatMetrics(MeterRegistry registry) {
        this.registry = registry;
        this.chatRequests = Counter.builder("chat.requests.total")
                .description("Chat stream requests started")
                .register(registry);
        this.chatStreamDuration = Timer.builder("chat.stream.duration")
                .description("End-to-end chat SSE duration")
                .publishPercentiles(0.5, 0.95, 0.99)
                .register(registry);
    }

    public void recordStart() {
        chatRequests.increment();
    }

    public void recordSuccess(long durationMs) {
        chatStreamDuration.record(Math.max(0, durationMs), TimeUnit.MILLISECONDS);
    }

    public void recordError(String code, long durationMs) {
        String safe = (code == null || code.isBlank()) ? "unknown" : code;
        errorCounters
                .computeIfAbsent(
                        safe,
                        c -> Counter.builder("chat.errors.total")
                                .description("Chat stream errors")
                                .tag("code", c)
                                .register(registry))
                .increment();
        if (durationMs >= 0) {
            chatStreamDuration.record(durationMs, TimeUnit.MILLISECONDS);
        }
    }
}
