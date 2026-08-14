package com.devops.copilot.modules.conversation.controller;

import com.devops.copilot.common.security.SecurityUtils;
import com.devops.copilot.modules.conversation.config.ChatProperties;
import com.devops.copilot.modules.conversation.controller.dto.ChatRequest;
import com.devops.copilot.modules.conversation.logging.ChatFlowLog;
import com.devops.copilot.modules.conversation.service.ChatService;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/sessions")
public class ChatController {

    private static final Logger log = LoggerFactory.getLogger(ChatController.class);

    private final ChatService chatService;
    private final ChatProperties chatProperties;

    public ChatController(ChatService chatService, ChatProperties chatProperties) {
        this.chatService = chatService;
        this.chatProperties = chatProperties;
    }

    /**
     * SSE 聊天入口。仅在建立连接时校验 JWT；流存续期间不因 Access 过期而中断。
     */
    @PostMapping(value = "/{sessionId}/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chat(
            @PathVariable UUID sessionId, @Valid @RequestBody ChatRequest request) {
        UserPrincipal principal = SecurityUtils.currentUser();
        // 全链路唯一一处打用户原文，后续步骤不再重复
        log.info(ChatFlowLog.msg(
                "01.接收",
                "sessionId=" + sessionId
                        + " userId=" + principal.getUserId()
                        + " teamId=" + principal.getTeamId()
                        + " clientMessageId=" + request.getClientMessageId()
                        + " chars=" + (request.getContent() == null ? 0 : request.getContent().length())
                        + " content=\"" + ChatFlowLog.preview(request.getContent()) + "\""));
        SseEmitter emitter = new SseEmitter(chatProperties.getSseTimeout().toMillis());
        chatService.streamChat(sessionId, request, principal, emitter);
        return emitter;
    }
}
