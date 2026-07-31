package com.devops.copilot.modules.file.domain.enums;

/**
 * 分析源文件类型（与 analysis_jobs.file_type CHECK 约束对齐）。
 */
public enum AnalysisFileType {
    HEAP_DUMP,
    GC_LOG,
    APP_LOG
}
