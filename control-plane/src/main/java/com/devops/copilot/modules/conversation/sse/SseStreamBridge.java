package com.devops.copilot.modules.conversation.sse;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;

/**
 * 把内部事件转成对客户端的 SSE。
 *
 * <p>生产建议每 15s 发 ping 保活；MVP 依赖 Tomcat/代理超时配置，此处仅注释提醒。
 */
@Component
public class SseStreamBridge {

    private static final Logger log = LoggerFactory.getLogger(SseStreamBridge.class);

    private final ObjectMapper objectMapper;

    public SseStreamBridge(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public void send(SseEmitter emitter, String eventName, Object data) {
        try {
            String json = data instanceof String s ? s : objectMapper.writeValueAsString(data);
            emitter.send(SseEmitter.event().name(eventName).data(json));
        } catch (IOException ex) {
            // 客户端已断开是常态，不打 error
            log.debug("SSE 发送失败（客户端可能已断开）: {}", ex.toString());
            throw new SseBrokenException(ex);
        }
    }

    public void sendError(SseEmitter emitter, String code, String message) {
        try {
            send(emitter, "error", Map.of("code", code, "message", message));
            emitter.complete();
        } catch (Exception ex) {
            emitter.completeWithError(ex);
        }
    }

    /** 标记 SSE 管道已断，供上层停止订阅。 */
    public static final class SseBrokenException extends RuntimeException {
        public SseBrokenException(Throwable cause) {
            super(cause);
        }
    }
}
