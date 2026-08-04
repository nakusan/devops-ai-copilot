package com.devops.copilot.observability.metrics;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ChatMetricsTest {

    @Test
    void recordsRequestAndSuccessDuration() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        ChatMetrics metrics = new ChatMetrics(registry);

        metrics.recordStart();
        metrics.recordSuccess(1200);

        assertEquals(1.0, registry.find("chat.requests.total").counter().count());
        assertTrue(registry.find("chat.stream.duration").timer().count() >= 1);
    }

    @Test
    void recordsErrorByCode() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        ChatMetrics metrics = new ChatMetrics(registry);

        metrics.recordError("LLM_TIMEOUT", 5000);

        assertEquals(1.0, registry.find("chat.errors.total").tag("code", "LLM_TIMEOUT").counter().count());
    }
}
