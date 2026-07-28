package com.devops.copilot.modules.conversation.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@ConfigurationProperties(prefix = "copilot.chat")
public class ChatProperties {

    private Duration sseTimeout = Duration.ofMinutes(5);
    private int defaultHistoryLimit = 20;
    private int estimateCharsPerToken = 4;

    public Duration getSseTimeout() {
        return sseTimeout;
    }

    public void setSseTimeout(Duration sseTimeout) {
        this.sseTimeout = sseTimeout;
    }

    public int getDefaultHistoryLimit() {
        return defaultHistoryLimit;
    }

    public void setDefaultHistoryLimit(int defaultHistoryLimit) {
        this.defaultHistoryLimit = defaultHistoryLimit;
    }

    public int getEstimateCharsPerToken() {
        return estimateCharsPerToken;
    }

    public void setEstimateCharsPerToken(int estimateCharsPerToken) {
        this.estimateCharsPerToken = estimateCharsPerToken;
    }
}
