package com.devops.copilot.modules.file.controller.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record IngestJobResponse(
        UUID jobId,
        UUID documentId,
        String status,
        Integer retryCount,
        String errorMessage,
        Long kafkaOffset,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
