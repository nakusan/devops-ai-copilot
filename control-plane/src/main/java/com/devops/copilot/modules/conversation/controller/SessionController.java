package com.devops.copilot.modules.conversation.controller;

import com.devops.copilot.common.security.SecurityUtils;
import com.devops.copilot.modules.conversation.controller.dto.CreateSessionRequest;
import com.devops.copilot.modules.conversation.controller.dto.SessionResponse;
import com.devops.copilot.modules.conversation.controller.dto.UpdateSessionRequest;
import com.devops.copilot.modules.conversation.service.SessionService;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/sessions")
public class SessionController {

    private final SessionService sessionService;

    public SessionController(SessionService sessionService) {
        this.sessionService = sessionService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public SessionResponse create(@Valid @RequestBody CreateSessionRequest request) {
        UserPrincipal user = SecurityUtils.currentUser();
        return sessionService.create(user.getUserId(), request);
    }

    @GetMapping
    public List<SessionResponse> list() {
        UserPrincipal user = SecurityUtils.currentUser();
        return sessionService.listMine(user.getUserId());
    }

    @GetMapping("/{id}")
    public SessionResponse get(@PathVariable UUID id) {
        UserPrincipal user = SecurityUtils.currentUser();
        return sessionService.getMine(id, user.getUserId());
    }

    @PatchMapping("/{id}")
    public SessionResponse update(@PathVariable UUID id, @Valid @RequestBody UpdateSessionRequest request) {
        UserPrincipal user = SecurityUtils.currentUser();
        return sessionService.update(id, user.getUserId(), request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID id) {
        UserPrincipal user = SecurityUtils.currentUser();
        sessionService.archive(id, user.getUserId());
    }
}
