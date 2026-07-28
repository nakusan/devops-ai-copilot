package com.devops.copilot.modules.conversation.controller;

import com.devops.copilot.common.security.SecurityUtils;
import com.devops.copilot.modules.conversation.controller.dto.AgentResponse;
import com.devops.copilot.modules.conversation.controller.dto.CreateAgentRequest;
import com.devops.copilot.modules.conversation.controller.dto.UpdateAgentRequest;
import com.devops.copilot.modules.conversation.service.AgentService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/agents")
public class AgentController {

    private final AgentService agentService;

    public AgentController(AgentService agentService) {
        this.agentService = agentService;
    }

    @GetMapping
    public List<AgentResponse> list() {
        SecurityUtils.currentUser();
        return agentService.list();
    }

    @GetMapping("/{id}")
    public AgentResponse get(@PathVariable Long id) {
        SecurityUtils.currentUser();
        return agentService.get(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize("hasRole('ADMIN')")
    public AgentResponse create(@Valid @RequestBody CreateAgentRequest request) {
        return agentService.create(request);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public AgentResponse update(@PathVariable Long id, @Valid @RequestBody UpdateAgentRequest request) {
        return agentService.update(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @PreAuthorize("hasRole('ADMIN')")
    public void delete(@PathVariable Long id) {
        agentService.delete(id);
    }
}
