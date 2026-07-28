package com.devops.copilot.modules.conversation.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class QuotaServiceTest {

    @Test
    void redisKeyFormat() {
        assertEquals("quota:team:1:daily_tokens", QuotaService.redisKey(1L));
    }
}
