package com.devops.copilot.modules.conversation.client.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * Java → Python 内部聊天请求（字段名 camelCase，与 FastAPI alias 对齐）。
 */
public class InternalChatRequest {

    private String traceId;
    private String sessionId;
    private String userMessage;
    private List<ChatMessageDto> history = new ArrayList<>();
    private AgentConfigDto agentConfig;
    private UserContextDto userContext;

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    public String getUserMessage() {
        return userMessage;
    }

    public void setUserMessage(String userMessage) {
        this.userMessage = userMessage;
    }

    public List<ChatMessageDto> getHistory() {
        return history;
    }

    public void setHistory(List<ChatMessageDto> history) {
        this.history = history;
    }

    public AgentConfigDto getAgentConfig() {
        return agentConfig;
    }

    public void setAgentConfig(AgentConfigDto agentConfig) {
        this.agentConfig = agentConfig;
    }

    public UserContextDto getUserContext() {
        return userContext;
    }

    public void setUserContext(UserContextDto userContext) {
        this.userContext = userContext;
    }

    public static class ChatMessageDto {
        private String role;
        private String content;

        public ChatMessageDto() {
        }

        public ChatMessageDto(String role, String content) {
            this.role = role;
            this.content = content;
        }

        public String getRole() {
            return role;
        }

        public void setRole(String role) {
            this.role = role;
        }

        public String getContent() {
            return content;
        }

        public void setContent(String content) {
            this.content = content;
        }
    }

    public static class UserContextDto {
        private Long userId;
        private Long teamId;

        public UserContextDto() {
        }

        public UserContextDto(Long userId, Long teamId) {
            this.userId = userId;
            this.teamId = teamId;
        }

        public Long getUserId() {
            return userId;
        }

        public void setUserId(Long userId) {
            this.userId = userId;
        }

        public Long getTeamId() {
            return teamId;
        }

        public void setTeamId(Long teamId) {
            this.teamId = teamId;
        }
    }

    public static class AgentConfigDto {
        private String model;
        private String systemPrompt;
        private boolean enableRag = true;
        private boolean enableMcp = true;
        private int ragTopK = 5;
        private double ragScoreThreshold = 0.7;
        private double temperature = 0.2;
        private int maxHistoryMessages = 20;
        private List<String> mcpServers = new ArrayList<>();
        private int llmTimeoutSeconds = 60;

        public String getModel() {
            return model;
        }

        public void setModel(String model) {
            this.model = model;
        }

        public String getSystemPrompt() {
            return systemPrompt;
        }

        public void setSystemPrompt(String systemPrompt) {
            this.systemPrompt = systemPrompt;
        }

        public boolean isEnableRag() {
            return enableRag;
        }

        public void setEnableRag(boolean enableRag) {
            this.enableRag = enableRag;
        }

        public boolean isEnableMcp() {
            return enableMcp;
        }

        public void setEnableMcp(boolean enableMcp) {
            this.enableMcp = enableMcp;
        }

        public int getRagTopK() {
            return ragTopK;
        }

        public void setRagTopK(int ragTopK) {
            this.ragTopK = ragTopK;
        }

        public double getRagScoreThreshold() {
            return ragScoreThreshold;
        }

        public void setRagScoreThreshold(double ragScoreThreshold) {
            this.ragScoreThreshold = ragScoreThreshold;
        }

        public double getTemperature() {
            return temperature;
        }

        public void setTemperature(double temperature) {
            this.temperature = temperature;
        }

        public int getMaxHistoryMessages() {
            return maxHistoryMessages;
        }

        public void setMaxHistoryMessages(int maxHistoryMessages) {
            this.maxHistoryMessages = maxHistoryMessages;
        }

        public List<String> getMcpServers() {
            return mcpServers;
        }

        public void setMcpServers(List<String> mcpServers) {
            this.mcpServers = mcpServers;
        }

        public int getLlmTimeoutSeconds() {
            return llmTimeoutSeconds;
        }

        public void setLlmTimeoutSeconds(int llmTimeoutSeconds) {
            this.llmTimeoutSeconds = llmTimeoutSeconds;
        }
    }
}
