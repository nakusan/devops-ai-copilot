package com.devops.copilot.common.exception;

/**
 * 可预期的业务异常。Controller / Service / Filter 统一抛出，
 * 由 {@link com.devops.copilot.common.exception.GlobalExceptionHandler} 转成 ErrorResponse。
 *
 * <p>不要用它包装未知系统故障——未知故障让 Handler 兜底为 INTERNAL_ERROR，避免泄露堆栈。
 */
public class BizException extends RuntimeException {

    private final ErrorCode errorCode;
    private final Object details;

    public BizException(ErrorCode errorCode) {
        super(errorCode.getDefaultMessage());
        this.errorCode = errorCode;
        this.details = null;
    }

    public BizException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
        this.details = null;
    }

    public BizException(ErrorCode errorCode, String message, Object details) {
        super(message);
        this.errorCode = errorCode;
        this.details = details;
    }

    public ErrorCode getErrorCode() {
        return errorCode;
    }

    public Object getDetails() {
        return details;
    }
}
