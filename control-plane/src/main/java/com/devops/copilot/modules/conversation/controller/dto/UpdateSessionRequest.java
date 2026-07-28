package com.devops.copilot.modules.conversation.controller.dto;

import jakarta.validation.constraints.Size;

/** 更新会话：可改标题或归档状态。 */
public class UpdateSessionRequest {

    @Size(max = 256)
    private String title;

    /** ACTIVE / ARCHIVED；null 表示不改。 */
    private String status;

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
