package com.devops.copilot.modules.file.controller.dto;

/** Python Worker 回调：更新 analysis_jobs。 */
public class UpdateAnalysisJobRequest {

    private String status;
    private String resultSummary;
    private String resultObjectKey;
    private String errorMessage;
    private Integer retryCount;

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getResultSummary() { return resultSummary; }
    public void setResultSummary(String resultSummary) { this.resultSummary = resultSummary; }
    public String getResultObjectKey() { return resultObjectKey; }
    public void setResultObjectKey(String resultObjectKey) { this.resultObjectKey = resultObjectKey; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public Integer getRetryCount() { return retryCount; }
    public void setRetryCount(Integer retryCount) { this.retryCount = retryCount; }
}
