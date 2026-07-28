package com.devops.copilot.modules.conversation.controller.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class ChatRequest {

    @NotBlank
    private String content;

    /** 客户端幂等键；同一 session 内重复提交应短路。 */
    @Size(max = 64)
    private String clientMessageId;

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public String getClientMessageId() {
        return clientMessageId;
    }

    public void setClientMessageId(String clientMessageId) {
        this.clientMessageId = clientMessageId;
    }
}
