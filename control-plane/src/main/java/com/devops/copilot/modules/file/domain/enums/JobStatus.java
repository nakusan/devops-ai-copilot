package com.devops.copilot.modules.file.domain.enums;

/**
 * 任务状态机：PENDING → PROCESSING → COMPLETED | FAILED。
 */
public enum JobStatus {
    PENDING,
    PROCESSING,
    COMPLETED,
    FAILED
}
