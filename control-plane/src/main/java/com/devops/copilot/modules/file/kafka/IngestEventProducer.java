package com.devops.copilot.modules.file.kafka;

import com.devops.copilot.modules.file.config.KafkaTopicProperties;
import com.devops.copilot.modules.file.kafka.event.AnalysisIngestEvent;
import com.devops.copilot.modules.file.kafka.event.KnowledgeIngestEvent;
import com.devops.copilot.modules.file.logging.IngestFlowLog;
import com.devops.copilot.observability.metrics.IngestMetrics;
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
    private final IngestMetrics ingestMetrics;

    public IngestEventProducer(
            KafkaTemplate<String, Object> kafkaTemplate,
            KafkaTopicProperties topicProperties,
            IngestMetrics ingestMetrics) {
        this.kafkaTemplate = kafkaTemplate;
        this.topicProperties = topicProperties;
        this.ingestMetrics = ingestMetrics;
    }

    public long publishKnowledgeIngest(KnowledgeIngestEvent event) {
        String topic = topicProperties.getTopics().getKnowledgeIngest();
        return send("knowledge", topic, event.getDocumentId().toString(), event, event.getJobId(), event.getTraceId());
    }

    public long publishAnalysisIngest(AnalysisIngestEvent event) {
        String topic = topicProperties.getTopics().getAnalysisIngest();
        send("analysis", topic, event.getJobId().toString(), event, event.getJobId(), event.getTraceId());
        return -1L;
    }

    public void publishKnowledgeDlq(KnowledgeIngestEvent event) {
        String topic = topicProperties.getTopics().getKnowledgeDlq();
        send("knowledge", topic, event.getDocumentId().toString(), event, event.getJobId(), event.getTraceId());
    }

    public void publishAnalysisDlq(AnalysisIngestEvent event) {
        String topic = topicProperties.getTopics().getAnalysisDlq();
        send("analysis", topic, event.getJobId().toString(), event, event.getJobId(), event.getTraceId());
    }

    private long send(
            String kind, String topic, String key, Object event, java.util.UUID jobId, String traceId) {
        log.info(IngestFlowLog.msg(
                kind,
                "06.kafka_send",
                "topic=" + topic + " key=" + key + " jobId=" + jobId + " traceId=" + traceId));
        try {
            CompletableFuture<SendResult<String, Object>> future = kafkaTemplate.send(topic, key, event);
            SendResult<String, Object> result = future.get(SEND_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            long offset = result.getRecordMetadata().offset();
            ingestMetrics.recordPublishSuccess(topic);
            log.info(IngestFlowLog.msg(
                    kind,
                    "06.kafka_ok",
                    "topic=" + topic + " key=" + key + " offset=" + offset + " jobId=" + jobId));
            return offset;
        } catch (Exception ex) {
            ingestMetrics.recordPublishFailure(topic);
            log.error(IngestFlowLog.msg(
                    kind,
                    "06.kafka_fail",
                    "topic=" + topic + " key=" + key + " jobId=" + jobId
                            + " error=\"" + IngestFlowLog.preview(ex.getMessage()) + "\""),
                    ex);
            throw new IllegalStateException("KAFKA_PUBLISH_FAILED: " + ex.getMessage(), ex);
        }
    }
}
