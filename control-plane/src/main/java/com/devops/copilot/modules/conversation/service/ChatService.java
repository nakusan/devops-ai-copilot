package com.devops.copilot.modules.conversation.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.common.trace.TraceIds;
import com.devops.copilot.modules.conversation.client.AiPlaneClient;
import com.devops.copilot.modules.conversation.client.dto.InternalChatRequest;
import com.devops.copilot.modules.conversation.client.dto.StreamEvent;
import com.devops.copilot.modules.conversation.config.ChatProperties;
import com.devops.copilot.modules.conversation.controller.dto.ChatRequest;
import com.devops.copilot.modules.conversation.domain.entity.Message;
import com.devops.copilot.modules.conversation.domain.entity.SessionEntity;
import com.devops.copilot.modules.conversation.domain.enums.MessageRole;
import com.devops.copilot.modules.conversation.mapper.MessageMapper;
import com.devops.copilot.modules.conversation.sse.SseStreamBridge;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import com.devops.copilot.observability.metrics.ChatMetrics;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import reactor.core.Disposable;
import reactor.core.scheduler.Schedulers;

import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 聊天编排：配额 → 落库 user → 调 Python → SSE 透传 → 落库 assistant。
 *
 * <p>SSE 终点在 Java（原则 P3），便于鉴权、审计与统一取消。
 */
@Service
public class ChatService {

    private static final Logger log = LoggerFactory.getLogger(ChatService.class);

    private final SessionService sessionService;
    private final AgentService agentService;
    private final MessageService messageService;
    private final MessageMapper messageMapper;
    private final QuotaService quotaService;
    private final AiPlaneClient aiPlaneClient;
    private final SseStreamBridge sseBridge;
    private final ChatProperties chatProperties;
    private final ObjectMapper objectMapper;
    private final ChatMetrics chatMetrics;

    public ChatService(
            SessionService sessionService,
            AgentService agentService,
            MessageService messageService,
            MessageMapper messageMapper,
            QuotaService quotaService,
            AiPlaneClient aiPlaneClient,
            SseStreamBridge sseBridge,
            ChatProperties chatProperties,
            ObjectMapper objectMapper,
            ChatMetrics chatMetrics) {
        this.sessionService = sessionService;
        this.agentService = agentService;
        this.messageService = messageService;
        this.messageMapper = messageMapper;
        this.quotaService = quotaService;
        this.aiPlaneClient = aiPlaneClient;
        this.sseBridge = sseBridge;
        this.chatProperties = chatProperties;
        this.objectMapper = objectMapper;
        this.chatMetrics = chatMetrics;
    }

    public void streamChat(
            UUID sessionId, ChatRequest req, UserPrincipal principal, SseEmitter emitter) {
        SessionEntity session = sessionService.requireOwnedSession(sessionId, principal.getUserId(), false);

        long estimate = Math.max(1, req.getContent().length() / Math.max(1, chatProperties.getEstimateCharsPerToken()));
        quotaService.assertWithinQuota(principal.getTeamId(), estimate);

        MessageService.SaveUserResult saved = messageService.saveUserMessage(sessionId, req);
        touchSession(session);

        // 幂等：已有完整 assistant 则直接回放 done，避免重复烧模型/Mock
        if (!saved.created()) {
            Message assistant = findAssistantAfter(sessionId, saved.message().getCreatedAt());
            if (assistant != null) {
                sseBridge.send(emitter, "done", Map.of(
                        "messageId", assistant.getId().toString(),
                        "idempotent", true,
                        "usage", assistant.getMetadataJson() != null
                                ? assistant.getMetadataJson().getOrDefault("usage", Map.of())
                                : Map.of()));
                emitter.complete();
                return;
            }
        }

        InternalChatRequest.AgentConfigDto agentConfig = agentService.getAgentForChat(session.getAgentId());
        int historyLimit = agentConfig.getMaxHistoryMessages() > 0
                ? agentConfig.getMaxHistoryMessages()
                : chatProperties.getDefaultHistoryLimit();
        List<InternalChatRequest.ChatMessageDto> history =
                messageService.loadHistory(sessionId, historyLimit, saved.message().getId());

        InternalChatRequest internal = new InternalChatRequest();
        internal.setTraceId(TraceIds.current());
        internal.setSessionId(sessionId.toString());
        internal.setUserMessage(req.getContent());
        internal.setHistory(history);
        internal.setAgentConfig(agentConfig);
        internal.setUserContext(new InternalChatRequest.UserContextDto(principal.getUserId(), principal.getTeamId()));

        StringBuilder buffer = new StringBuilder();
        AtomicReference<JsonNode> doneRef = new AtomicReference<>();
        AtomicBoolean finished = new AtomicBoolean(false);
        long startedAt = System.currentTimeMillis();
        AtomicLong startedAtRef = new AtomicLong(startedAt);
        chatMetrics.recordStart();
        log.info(
                "event=chat.stream.start sessionId={} traceId={}",
                sessionId,
                TraceIds.current());

        // 在弹性线程订阅，避免阻塞 Tomcat 请求线程过久（SseEmitter 已返回）
        Disposable subscription = aiPlaneClient.streamChat(internal)
                .publishOn(Schedulers.boundedElastic())
                .subscribe(
                        evt -> onEvent(emitter, buffer, doneRef, finished, startedAtRef, evt),
                        err -> onError(emitter, sessionId, finished, startedAtRef, err),
                        () -> onComplete(
                                emitter,
                                sessionId,
                                principal.getTeamId(),
                                buffer,
                                doneRef,
                                finished,
                                startedAtRef));

        emitter.onCompletion(() -> cleanup(subscription, sessionId, finished));
        emitter.onTimeout(() -> {
            cleanup(subscription, sessionId, finished);
            emitter.complete();
        });
        emitter.onError(ex -> cleanup(subscription, sessionId, finished));
    }

    private void onEvent(
            SseEmitter emitter,
            StringBuilder buffer,
            AtomicReference<JsonNode> doneRef,
            AtomicBoolean finished,
            AtomicLong startedAtRef,
            StreamEvent evt) {
        try {
            switch (evt.getType()) {
                case "token" -> {
                    if (evt.getText() != null) {
                        buffer.append(evt.getText());
                        sseBridge.send(emitter, "token", Map.of("text", evt.getText()));
                    }
                }
                case "citation" -> sseBridge.send(emitter, "citation", evt.getData());
                case "done" -> doneRef.set(evt.getDone());
                case "error" -> {
                    if (!finished.compareAndSet(false, true)) {
                        return;
                    }
                    String code = evt.getError() != null && evt.getError().has("code")
                            ? evt.getError().get("code").asText()
                            : "AGENT_ERROR";
                    String message = evt.getError() != null && evt.getError().has("message")
                            ? evt.getError().get("message").asText()
                            : "上游生成失败";
                    long durationMs = System.currentTimeMillis() - startedAtRef.get();
                    chatMetrics.recordError(code, durationMs);
                    log.warn(
                            "event=chat.stream.end status=error code={} durationMs={} traceId={}",
                            code,
                            durationMs,
                            TraceIds.current());
                    sseBridge.sendError(emitter, code, message);
                }
                default -> log.debug("忽略未知流事件 type={}", evt.getType());
            }
        } catch (SseStreamBridge.SseBrokenException broken) {
            // 客户端断开：停止处理后续事件（subscription 会在 onCompletion 清理）
            throw broken;
        }
    }

    private void onComplete(
            SseEmitter emitter,
            UUID sessionId,
            Long teamId,
            StringBuilder buffer,
            AtomicReference<JsonNode> doneRef,
            AtomicBoolean finished,
            AtomicLong startedAtRef) {
        if (!finished.compareAndSet(false, true)) {
            return;
        }
        long durationMs = System.currentTimeMillis() - startedAtRef.get();
        try {
            Map<String, Object> metadata = new HashMap<>();
            JsonNode done = doneRef.get();
            long usageTotal = 0;
            if (done != null) {
                metadata = objectMapper.convertValue(done, new TypeReference<>() {
                });
                if (done.has("usage") && done.get("usage").has("totalTokens")) {
                    usageTotal = done.get("usage").get("totalTokens").asLong();
                }
            }
            Message assistant = messageService.saveAssistantMessage(sessionId, buffer.toString(), metadata);
            if (usageTotal > 0) {
                quotaService.increaseUsage(teamId, usageTotal);
            }
            chatMetrics.recordSuccess(durationMs);
            log.info(
                    "event=chat.stream.end status=success sessionId={} durationMs={} tokenCount={} traceId={}",
                    sessionId,
                    durationMs,
                    usageTotal,
                    TraceIds.current());
            sseBridge.send(emitter, "done", Map.of(
                    "messageId", assistant.getId().toString(),
                    "usage", metadata.getOrDefault("usage", Map.of())));
            emitter.complete();
        } catch (SseStreamBridge.SseBrokenException broken) {
            log.debug("完成阶段客户端已断开");
        } catch (Exception ex) {
            chatMetrics.recordError(ErrorCode.INTERNAL_ERROR.getCode(), durationMs);
            log.error("流结束落库失败", ex);
            sseBridge.sendError(emitter, ErrorCode.INTERNAL_ERROR.getCode(), "保存回复失败");
        }
    }

    private void onError(
            SseEmitter emitter, UUID sessionId, AtomicBoolean finished, AtomicLong startedAtRef, Throwable err) {
        if (!finished.compareAndSet(false, true)) {
            return;
        }
        long durationMs = System.currentTimeMillis() - startedAtRef.get();
        log.warn("聊天流失败 sessionId={}: {}", sessionId, err.toString());
        if (err instanceof BizException biz) {
            chatMetrics.recordError(biz.getErrorCode().getCode(), durationMs);
            sseBridge.sendError(emitter, biz.getErrorCode().getCode(), biz.getMessage());
        } else {
            chatMetrics.recordError(ErrorCode.INTERNAL_ERROR.getCode(), durationMs);
            sseBridge.sendError(emitter, ErrorCode.INTERNAL_ERROR.getCode(), "上游流式调用失败");
        }
    }

    private void cleanup(Disposable subscription, UUID sessionId, AtomicBoolean finished) {
        if (subscription != null && !subscription.isDisposed()) {
            subscription.dispose();
        }
        // 仅在流未正常结束时通知 Python 取消，避免多余 cancel
        if (!finished.get()) {
            aiPlaneClient.cancel(sessionId.toString(), TraceIds.current());
            finished.set(true);
        }
    }

    private void touchSession(SessionEntity session) {
        sessionService.touchUpdatedAt(session.getId());
    }

    private Message findAssistantAfter(UUID sessionId, OffsetDateTime after) {
        return messageMapper.selectOne(new LambdaQueryWrapper<Message>()
                .eq(Message::getSessionId, sessionId)
                .eq(Message::getRole, MessageRole.assistant.name())
                .gt(Message::getCreatedAt, after)
                .orderByAsc(Message::getCreatedAt)
                .last("LIMIT 1"));
    }
}
