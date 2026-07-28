package com.devops.copilot.modules.conversation.controller;

import com.devops.copilot.common.security.SecurityUtils;
import com.devops.copilot.modules.conversation.config.ChatProperties;
import com.devops.copilot.modules.conversation.controller.dto.ChatRequest;
import com.devops.copilot.modules.conversation.service.ChatService;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import jakarta.validation.Valid;
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
        SseEmitter emitter = new SseEmitter(chatProperties.getSseTimeout().toMillis());
        chatService.streamChat(sessionId, request, principal, emitter);
        return emitter;
    }
}
