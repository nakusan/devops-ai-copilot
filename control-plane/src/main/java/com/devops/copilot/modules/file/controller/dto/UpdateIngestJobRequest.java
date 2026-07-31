package com.devops.copilot.modules.file.controller.dto;

/** Python Worker 回调：更新 ingest_jobs（并镜像 documents）。 */
public class UpdateIngestJobRequest {

    private String status;
    private String errorMessage;
    private Integer retryCount;

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public Integer getRetryCount() { return retryCount; }
    public void setRetryCount(Integer retryCount) { this.retryCount = retryCount; }
}
