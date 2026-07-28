package com.devops.copilot.modules.conversation.controller.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record SessionResponse(
        UUID id,
        Long userId,
        Long agentId,
        String title,
        String status,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
