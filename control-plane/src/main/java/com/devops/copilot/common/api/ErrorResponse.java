package com.devops.copilot.common.api;

import java.time.Instant;

/**
 * 统一 API 错误响应体（参考 RFC 7807 / Stripe 风格）。
 *
 * <p>所有业务异常与安全失败经 {@code GlobalExceptionHandler} 转成此结构，
 * 保证客户端与排障方只解析一种错误形状。
 */
public class ErrorResponse {

    /** 机器可读错误码，如 {@code AUTH_INVALID}、{@code RATE_LIMITED}。 */
    private String code;

    /** 可安全返回给客户端的可读说明（不泄露内部细节）。 */
    private String message;

    /** 链路追踪 ID（W3C / MDC），用于排障与日志关联。 */
    private String traceId;

    /** 错误发生时间（UTC）。 */
    private Instant timestamp;

    /** 可选：字段级校验细节。 */
    private Object details;

    public static ErrorResponse of(String code, String message, String traceId) {
        ErrorResponse r = new ErrorResponse();
        r.code = code;
        r.message = message;
        r.traceId = traceId;
        r.timestamp = Instant.now();
        return r;
    }

    public static ErrorResponse of(String code, String message, String traceId, Object details) {
        ErrorResponse r = of(code, message, traceId);
        r.details = details;
        return r;
    }

    public String getCode() {
        return code;
    }

    public void setCode(String code) {
        this.code = code;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public Instant getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(Instant timestamp) {
        this.timestamp = timestamp;
    }

    public Object getDetails() {
        return details;
    }

    public void setDetails(Object details) {
        this.details = details;
    }
}
