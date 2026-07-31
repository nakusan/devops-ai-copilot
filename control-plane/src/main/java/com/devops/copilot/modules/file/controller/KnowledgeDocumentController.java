package com.devops.copilot.modules.file.controller;

import com.devops.copilot.common.security.SecurityUtils;
import com.devops.copilot.modules.conversation.controller.dto.PageResponse;
import com.devops.copilot.modules.file.controller.dto.IngestResponse;
import com.devops.copilot.modules.file.controller.dto.KnowledgeDocumentResponse;
import com.devops.copilot.modules.file.service.KnowledgeIngestService;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/knowledge/documents")
public class KnowledgeDocumentController {

    private final KnowledgeIngestService knowledgeIngestService;

    public KnowledgeDocumentController(KnowledgeIngestService knowledgeIngestService) {
        this.knowledgeIngestService = knowledgeIngestService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.ACCEPTED)
    public IngestResponse upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "title", required = false) String title) {
        UserPrincipal user = SecurityUtils.currentUser();
        return knowledgeIngestService.ingest(file, user.getUserId(), user.getTeamId(), title);
    }

    @GetMapping("/{id}")
    public KnowledgeDocumentResponse get(@PathVariable("id") UUID id) {
        UserPrincipal user = SecurityUtils.currentUser();
        return knowledgeIngestService.getMine(id, user.getUserId());
    }

    @GetMapping
    public PageResponse<KnowledgeDocumentResponse> list(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        UserPrincipal user = SecurityUtils.currentUser();
        return knowledgeIngestService.listMine(user.getUserId(), page, size);
    }
}
