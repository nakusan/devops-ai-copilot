package com.devops.copilot.modules.conversation.client;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.common.trace.TraceIds;
import com.devops.copilot.modules.conversation.client.dto.CancelChatRequest;
import com.devops.copilot.modules.conversation.client.dto.InternalChatRequest;
import com.devops.copilot.modules.conversation.client.dto.StreamEvent;
import com.devops.copilot.modules.conversation.logging.ChatFlowLog;
import com.devops.copilot.modules.security.jwt.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

/**
 * 调用 AI Plane 的 WebClient 封装。
 *
 * <p><b>流式请求故意不做重试</b>：重试会让下游再次生成，客户端收到重复 token。
 * 失败应返回 error 事件，由用户决定是否重发。
 *
 * <p>W3C {@code traceparent} 由 Micrometer Observation + 注入的 {@link WebClient.Builder}
 * 自动注入（设计 6.10 §6.5）。切勿改成 {@code WebClient.create()}，否则传播会静默失效。
 * 业务头 {@code X-Trace-Id} 仍手动附带，供 Python 记为 {@code copilot.trace_id}。
 */
@Component
public class AiPlaneClient {

    private static final Logger log = LoggerFactory.getLogger(AiPlaneClient.class);
    private static final MediaType NDJSON = MediaType.parseMediaType("application/x-ndjson");

    private final WebClient aiPlaneWebClient;
    private final ServiceTokenProvider serviceTokenProvider;
    private final ObjectMapper objectMapper;

    public AiPlaneClient(
            WebClient aiPlaneWebClient,
            ServiceTokenProvider serviceTokenProvider,
            ObjectMapper objectMapper) {
        this.aiPlaneWebClient = aiPlaneWebClient;
        this.serviceTokenProvider = serviceTokenProvider;
        this.objectMapper = objectMapper;
    }

    /**
     * 订阅 NDJSON 流：按行拆分后反序列化为 {@link StreamEvent}。
     *
     * <p>使用 {@code bodyToFlux(String.class)} 依赖 WebClient 对文本流的行缓冲；
     * 若上游未换行 flush，客户端会卡住——Mock/LLM 实现必须每事件一行并换行。
     */
    public Flux<StreamEvent> streamChat(InternalChatRequest request) {
        String token = serviceTokenProvider.issue();
        String traceId = request.getTraceId() != null ? request.getTraceId() : TraceIds.current();

        int historyCount = request.getHistory() == null ? 0 : request.getHistory().size();
        String model = request.getAgentConfig() != null ? request.getAgentConfig().getModel() : null;
        log.info(ChatFlowLog.msg(
                "05.出站HTTP",
                "sessionId=" + request.getSessionId()
                        + " model=" + model
                        + " historyCount=" + historyCount
                        + " user=\"" + ChatFlowLog.preview(request.getUserMessage()) + "\""));

        return aiPlaneWebClient.post()
                .uri("/internal/v1/chat/stream")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(NDJSON)
                .header(ServiceTokenProvider.HEADER, token)
                // traceparent：ObservationWebClientCustomizer 自动注入；勿手拼
                .header(TraceIds.HEADER_X_TRACE_ID, traceId)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class)
                .filter(line -> line != null && !line.isBlank())
                .map(this::parseLine)
                .doOnError(err -> log.warn(ChatFlowLog.msg(
                        "05.出站HTTP失败",
                        "sessionId=" + request.getSessionId()
                                + " error=\"" + ChatFlowLog.preview(err.toString()) + "\"")));
    }

    public void cancel(String sessionId, String traceId) {
        try {
            log.info(ChatFlowLog.msg("08.取消上游", "sessionId=" + sessionId));
            aiPlaneWebClient.post()
                    .uri("/internal/v1/chat/cancel")
                    .contentType(MediaType.APPLICATION_JSON)
                    .header(ServiceTokenProvider.HEADER, serviceTokenProvider.issue())
                    .header(TraceIds.HEADER_X_TRACE_ID, traceId != null ? traceId : TraceIds.current())
                    .bodyValue(new CancelChatRequest(sessionId, traceId))
                    .retrieve()
                    .toBodilessEntity()
                    .block();
        } catch (Exception ex) {
            log.debug(ChatFlowLog.msg(
                    "08.取消上游失败",
                    "sessionId=" + sessionId + " error=\"" + ChatFlowLog.preview(ex.toString()) + "\""));
        }
    }

    private StreamEvent parseLine(String line) {
        try {
            return objectMapper.readValue(line, StreamEvent.class);
        } catch (Exception ex) {
            throw new BizException(ErrorCode.INTERNAL_ERROR, "无法解析 AI Plane NDJSON: " + line);
        }
    }
}
