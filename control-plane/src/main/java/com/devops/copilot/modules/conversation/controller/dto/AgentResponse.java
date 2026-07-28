package com.devops.copilot.modules.conversation.controller.dto;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;

public record AgentResponse(
        Long id,
        String name,
        String model,
        String systemPrompt,
        Boolean enableRag,
        Boolean enableMcp,
        Integer ragTopK,
        BigDecimal temperature,
        Map<String, Object> configJson,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
