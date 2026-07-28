package com.devops.copilot.modules.conversation.client.dto;

/** 取消请求体。 */
public class CancelChatRequest {

    private String sessionId;
    private String traceId;

    public CancelChatRequest() {
    }

    public CancelChatRequest(String sessionId, String traceId) {
        this.sessionId = sessionId;
        this.traceId = traceId;
    }

    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }
}
