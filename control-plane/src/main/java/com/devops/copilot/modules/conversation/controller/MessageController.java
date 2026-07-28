package com.devops.copilot.modules.conversation.controller;

import com.devops.copilot.common.security.SecurityUtils;
import com.devops.copilot.modules.conversation.controller.dto.MessageResponse;
import com.devops.copilot.modules.conversation.controller.dto.PageResponse;
import com.devops.copilot.modules.conversation.service.MessageService;
import com.devops.copilot.modules.conversation.service.SessionService;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/sessions")
public class MessageController {

    private final SessionService sessionService;
    private final MessageService messageService;

    public MessageController(SessionService sessionService, MessageService messageService) {
        this.sessionService = sessionService;
        this.messageService = messageService;
    }

    @GetMapping("/{sessionId}/messages")
    public PageResponse<MessageResponse> list(
            @PathVariable UUID sessionId,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        UserPrincipal user = SecurityUtils.currentUser();
        // 允许查看已归档会话的历史
        sessionService.requireOwnedSession(sessionId, user.getUserId(), true);
        return messageService.listBySession(sessionId, page, size);
    }
}
