package com.devops.copilot.modules.file.controller.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record AnalysisJobResponse(
        UUID jobId,
        String fileType,
        String status,
        String resultSummary,
        String errorMessage,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
