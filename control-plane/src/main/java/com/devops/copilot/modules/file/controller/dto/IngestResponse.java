package com.devops.copilot.modules.file.controller.dto;

import java.util.UUID;

public record IngestResponse(
        UUID documentId,
        UUID jobId,
        String status
) {
}
