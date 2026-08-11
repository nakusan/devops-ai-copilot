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
import com.devops.copilot.modules.conversation.logging.ChatFlowLog;
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
import java.util.concurrent.atomic.AtomicInteger;
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
        log.info(ChatFlowLog.msg(
                "01.会话信息获取",
                "sessionId=" + sessionId
                        + " agentId=" + session.getAgentId()
                        + " title=\"" + ChatFlowLog.preview(session.getTitle()) + "\""));

        long estimate = Math.max(1, req.getContent().length() / Math.max(1, chatProperties.getEstimateCharsPerToken()));
        quotaService.assertWithinQuota(principal.getTeamId(), estimate);

        MessageService.SaveUserResult saved = messageService.saveUserMessage(sessionId, req);
        touchSession(session);
        log.info(ChatFlowLog.msg(
                "03.用户消息保存",
                "messageId=" + saved.message().getId()
                        + " created=" + saved.created()
                        + " clientMessageId=" + saved.message().getClientMessageId()
                        + " chars=" + (saved.message().getContent() == null ? 0 : saved.message().getContent().length())
                        + " content=\"" + ChatFlowLog.preview(saved.message().getContent()) + "\""));

        // 幂等：已有完整 assistant 则直接回放 done，避免重复烧模型/Mock
        if (!saved.created()) {
            Message assistant = findAssistantAfter(sessionId, saved.message().getCreatedAt());
            if (assistant != null) {
                log.info(ChatFlowLog.msg(
                        "03.幂等回放",
                        "sessionId=" + sessionId
                                + " userMessageId=" + saved.message().getId()
                                + " assistantMessageId=" + assistant.getId()
                                + " chars=" + (assistant.getContent() == null ? 0 : assistant.getContent().length())));
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

        log.info(ChatFlowLog.msg(
                "04.准备上下文",
                "agentId=" + session.getAgentId()
                        + " model=" + agentConfig.getModel()
                        + " enableRag=" + agentConfig.isEnableRag()
                        + " enableMcp=" + agentConfig.isEnableMcp()
                        + " historyCount=" + history.size()
                        + " historyLimit=" + historyLimit));

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
        AtomicInteger tokenEvents = new AtomicInteger(0);
        long startedAt = System.currentTimeMillis();
        AtomicLong startedAtRef = new AtomicLong(startedAt);
        chatMetrics.recordStart();
        log.info(ChatFlowLog.msg(
                "05.调用AI模型",
                "sessionId=" + sessionId
                        + " historyCount=" + history.size()
                        + " userChars=" + req.getContent().length()));

        Disposable subscription = aiPlaneClient.streamChat(internal)
                .publishOn(Schedulers.boundedElastic())
                .subscribe(
                        evt -> onEvent(emitter, buffer, doneRef, finished, startedAtRef, tokenEvents, evt),
                        err -> onError(emitter, sessionId, finished, startedAtRef, err),
                        () -> onComplete(
                                emitter,
                                sessionId,
                                principal.getTeamId(),
                                buffer,
                                doneRef,
                                finished,
                                startedAtRef,
                                tokenEvents));

        emitter.onCompletion(() -> cleanup(subscription, sessionId, finished));
        emitter.onTimeout(() -> {
            log.warn(ChatFlowLog.msg("08.SSE超时", "sessionId=" + sessionId));
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
            AtomicInteger tokenEvents,
            StreamEvent evt) {
        try {
            switch (evt.getType()) {
                case "token" -> {
                    if (evt.getText() != null) {
                        buffer.append(evt.getText());
                        int n = tokenEvents.incrementAndGet();
                        // 首个 token + 每 20 个打一次，避免刷屏
                        if (n == 1 || n % 20 == 0) {
                            log.info(ChatFlowLog.msg(
                                    "06.接收Token",
                                    "n=" + n
                                            + " bufChars=" + buffer.length()
                                            + " chunk=\"" + ChatFlowLog.preview(evt.getText()) + "\""));
                        }
                        sseBridge.send(emitter, "token", Map.of("text", evt.getText()));
                    }
                }
                case "citation" -> {
                    JsonNode data = evt.getData();
                    int chunkCount = 0;
                    if (data != null && data.has("citations") && data.get("citations").isArray()) {
                        chunkCount = data.get("citations").size();
                    } else if (data != null && data.has("chunks") && data.get("chunks").isArray()) {
                        chunkCount = data.get("chunks").size();
                    }
                    log.info(ChatFlowLog.msg(
                            "06.接收引用",
                            "chunks=" + chunkCount + " data=" + ChatFlowLog.preview(String.valueOf(data))));
                    sseBridge.send(emitter, "citation", evt.getData());
                }
                case "done" -> {
                    doneRef.set(evt.getDone());
                    log.info(ChatFlowLog.msg(
                            "06.上游完成",
                            "payload=" + ChatFlowLog.preview(String.valueOf(evt.getDone()))));
                }
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
                    log.warn(ChatFlowLog.msg(
                            "08.结束",
                            "status=error code=" + code
                                    + " message=\"" + ChatFlowLog.preview(message) + "\""
                                    + " durationMs=" + durationMs
                                    + " tokenEvents=" + tokenEvents.get()
                                    + " bufChars=" + buffer.length()));
                    sseBridge.sendError(emitter, code, message);
                }
                default -> log.debug(ChatFlowLog.msg("06.未知事件", "type=" + evt.getType()));
            }
        } catch (SseStreamBridge.SseBrokenException broken) {
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
            AtomicLong startedAtRef,
            AtomicInteger tokenEvents) {
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
            log.info(ChatFlowLog.msg(
                    "07.助手消息保存",
                    "messageId=" + assistant.getId()
                            + " chars=" + buffer.length()
                            + " tokenEvents=" + tokenEvents.get()
                            + " usageTotal=" + usageTotal
                            + " content=\"" + ChatFlowLog.preview(buffer.toString()) + "\""));
            log.info(ChatFlowLog.msg(
                    "08.结束",
                    "status=success sessionId=" + sessionId
                            + " durationMs=" + durationMs
                            + " assistantMessageId=" + assistant.getId()
                            + " usageTotal=" + usageTotal));
            sseBridge.send(emitter, "done", Map.of(
                    "messageId", assistant.getId().toString(),
                    "usage", metadata.getOrDefault("usage", Map.of())));
            emitter.complete();
        } catch (SseStreamBridge.SseBrokenException broken) {
            log.debug(ChatFlowLog.msg("08.客户端已断开", "sessionId=" + sessionId));
        } catch (Exception ex) {
            chatMetrics.recordError(ErrorCode.INTERNAL_ERROR.getCode(), durationMs);
            log.error(ChatFlowLog.msg("08.结束", "status=persist_fail sessionId=" + sessionId), ex);
            sseBridge.sendError(emitter, ErrorCode.INTERNAL_ERROR.getCode(), "保存回复失败");
        }
    }

    private void onError(
            SseEmitter emitter, UUID sessionId, AtomicBoolean finished, AtomicLong startedAtRef, Throwable err) {
        if (!finished.compareAndSet(false, true)) {
            return;
        }
        long durationMs = System.currentTimeMillis() - startedAtRef.get();
        log.warn(ChatFlowLog.msg(
                "08.结束",
                "status=upstream_fail sessionId=" + sessionId
                        + " durationMs=" + durationMs
                        + " error=\"" + ChatFlowLog.preview(err.toString()) + "\""));
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
        if (!finished.get()) {
            log.info(ChatFlowLog.msg("08.取消", "sessionId=" + sessionId + " reason=client_disconnect"));
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
