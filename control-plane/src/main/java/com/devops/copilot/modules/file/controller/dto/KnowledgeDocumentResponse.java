package com.devops.copilot.modules.file.controller.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record KnowledgeDocumentResponse(
        UUID documentId,
        String title,
        String mimeType,
        Long sizeBytes,
        String status,
        String errorMessage,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
