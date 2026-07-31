package com.devops.copilot.modules.file.kafka;

import com.devops.copilot.modules.file.config.KafkaTopicProperties;
import com.devops.copilot.modules.file.kafka.event.AnalysisIngestEvent;
import com.devops.copilot.modules.file.kafka.event.KnowledgeIngestEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

/**
 * Kafka 生产者：知识入库与大文件分析事件。
 *
 * <p>MVP 同步等待 send 结果（超时失败则标 FAILED）。生产可改为 Outbox。
 */
@Component
public class IngestEventProducer {

    private static final Logger log = LoggerFactory.getLogger(IngestEventProducer.class);
    private static final long SEND_TIMEOUT_SECONDS = 10;

    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final KafkaTopicProperties topicProperties;

    public IngestEventProducer(
            KafkaTemplate<String, Object> kafkaTemplate, KafkaTopicProperties topicProperties) {
        this.kafkaTemplate = kafkaTemplate;
        this.topicProperties = topicProperties;
    }

    public long publishKnowledgeIngest(KnowledgeIngestEvent event) {
        String topic = topicProperties.getTopics().getKnowledgeIngest();
        // key=documentId：同文档消息落到同一分区，保证有序
        return send(topic, event.getDocumentId().toString(), event);
    }

    public long publishAnalysisIngest(AnalysisIngestEvent event) {
        String topic = topicProperties.getTopics().getAnalysisIngest();
        return send(topic, event.getJobId().toString(), event);
    }

    public void publishKnowledgeDlq(KnowledgeIngestEvent event) {
        send(topicProperties.getTopics().getKnowledgeDlq(), event.getDocumentId().toString(), event);
    }

    public void publishAnalysisDlq(AnalysisIngestEvent event) {
        send(topicProperties.getTopics().getAnalysisDlq(), event.getJobId().toString(), event);
    }

    private long send(String topic, String key, Object event) {
        try {
            CompletableFuture<SendResult<String, Object>> future = kafkaTemplate.send(topic, key, event);
            SendResult<String, Object> result = future.get(SEND_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            long offset = result.getRecordMetadata().offset();
            log.info("kafka published topic={} key={} offset={}", topic, key, offset);
            return offset;
        } catch (Exception ex) {
            log.error("kafka publish failed topic={} key={}", topic, key, ex);
            throw new IllegalStateException("KAFKA_PUBLISH_FAILED: " + ex.getMessage(), ex);
        }
    }
}
