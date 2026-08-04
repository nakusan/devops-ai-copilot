package com.devops.copilot.observability.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;

/**
 * Kafka / 异步入库投递指标（设计 6.7 §3.3.6）。
 */
@Component
public class IngestMetrics {

    private final MeterRegistry registry;
    private final ConcurrentHashMap<String, Counter> publishCounters = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Counter> failureCounters = new ConcurrentHashMap<>();

    public IngestMetrics(MeterRegistry registry) {
        this.registry = registry;
    }

    public void recordPublishSuccess(String topic) {
        String t = sanitize(topic);
        publishCounters
                .computeIfAbsent(
                        t,
                        name -> Counter.builder("kafka.publish.total")
                                .description("Kafka publish successes")
                                .tag("topic", name)
                                .register(registry))
                .increment();
    }

    public void recordPublishFailure(String topic) {
        String t = sanitize(topic);
        failureCounters
                .computeIfAbsent(
                        t,
                        name -> Counter.builder("kafka.publish.failures.total")
                                .description("Kafka publish failures")
                                .tag("topic", name)
                                .register(registry))
                .increment();
    }

    private static String sanitize(String topic) {
        return (topic == null || topic.isBlank()) ? "unknown" : topic;
    }
}
