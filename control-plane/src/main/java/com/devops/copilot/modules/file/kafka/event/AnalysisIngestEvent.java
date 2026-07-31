package com.devops.copilot.modules.file.kafka.event;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Kafka analysis.ingest.v1 事件体。
 */
public class AnalysisIngestEvent {

    private UUID eventId;
    private String eventType = "ANALYSIS_INGEST";
    private UUID jobId;
    private Long userId;
    private Long teamId;
    private String objectKey;
    private String fileType;
    private String traceId;
    private OffsetDateTime createdAt;

    public UUID getEventId() { return eventId; }
    public void setEventId(UUID eventId) { this.eventId = eventId; }
    public String getEventType() { return eventType; }
    public void setEventType(String eventType) { this.eventType = eventType; }
    public UUID getJobId() { return jobId; }
    public void setJobId(UUID jobId) { this.jobId = jobId; }
    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }
    public Long getTeamId() { return teamId; }
    public void setTeamId(Long teamId) { this.teamId = teamId; }
    public String getObjectKey() { return objectKey; }
    public void setObjectKey(String objectKey) { this.objectKey = objectKey; }
    public String getFileType() { return fileType; }
    public void setFileType(String fileType) { this.fileType = fileType; }
    public String getTraceId() { return traceId; }
    public void setTraceId(String traceId) { this.traceId = traceId; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime createdAt) { this.createdAt = createdAt; }
}
