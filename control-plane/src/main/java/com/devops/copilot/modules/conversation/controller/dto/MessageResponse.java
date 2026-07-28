package com.devops.copilot.modules.conversation.controller.dto;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record MessageResponse(
        UUID id,
        UUID sessionId,
        String role,
        String content,
        Integer tokenCount,
        Map<String, Object> metadataJson,
        String clientMessageId,
        OffsetDateTime createdAt
) {
}
