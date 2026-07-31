package com.devops.copilot.common.exception;

import org.springframework.http.HttpStatus;

/**
 * 业务错误码：code 写进响应体，status 决定 HTTP 状态。
 *
 * <p>与详细设计 §9 错误模型对齐；新增错误码时同步更新文档。
 */
public enum ErrorCode {

    AUTH_INVALID("AUTH_INVALID", "认证失败", HttpStatus.UNAUTHORIZED),
    TOKEN_EXPIRED("TOKEN_EXPIRED", "令牌已过期", HttpStatus.UNAUTHORIZED),
    FORBIDDEN("FORBIDDEN", "无权限访问该资源", HttpStatus.FORBIDDEN),
    NOT_FOUND("NOT_FOUND", "资源不存在", HttpStatus.NOT_FOUND),
    VALIDATION_ERROR("VALIDATION_ERROR", "参数校验失败", HttpStatus.BAD_REQUEST),
    RATE_LIMITED("RATE_LIMITED", "请求过于频繁，请稍后再试", HttpStatus.TOO_MANY_REQUESTS),
    QUOTA_EXCEEDED("QUOTA_EXCEEDED", "今日 Token 配额已用尽", HttpStatus.TOO_MANY_REQUESTS),
    CONFLICT("CONFLICT", "资源冲突", HttpStatus.CONFLICT),
    UNSUPPORTED_FILE_TYPE("UNSUPPORTED_FILE_TYPE", "不支持的文件类型", HttpStatus.BAD_REQUEST),
    FILE_TOO_LARGE("FILE_TOO_LARGE", "文件超过大小限制", HttpStatus.BAD_REQUEST),
    INGEST_PUBLISH_FAILED("INGEST_PUBLISH_FAILED", "任务已登记但消息投递失败", HttpStatus.INTERNAL_SERVER_ERROR),
    STORAGE_ERROR("STORAGE_ERROR", "对象存储操作失败", HttpStatus.INTERNAL_SERVER_ERROR),
    INTERNAL_ERROR("INTERNAL_ERROR", "服务内部错误", HttpStatus.INTERNAL_SERVER_ERROR);

    private final String code;
    private final String defaultMessage;
    private final HttpStatus status;

    ErrorCode(String code, String defaultMessage, HttpStatus status) {
        this.code = code;
        this.defaultMessage = defaultMessage;
        this.status = status;
    }

    public String getCode() {
        return code;
    }

    public String getDefaultMessage() {
        return defaultMessage;
    }

    public HttpStatus getStatus() {
        return status;
    }
}
