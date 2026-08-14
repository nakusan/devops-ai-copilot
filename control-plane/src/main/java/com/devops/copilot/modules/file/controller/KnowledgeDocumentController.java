package com.devops.copilot.modules.file.controller;

import com.devops.copilot.common.security.SecurityUtils;
import com.devops.copilot.modules.conversation.controller.dto.PageResponse;
import com.devops.copilot.modules.file.controller.dto.IngestResponse;
import com.devops.copilot.modules.file.controller.dto.KnowledgeDocumentResponse;
import com.devops.copilot.modules.file.logging.IngestFlowLog;
import com.devops.copilot.modules.file.service.KnowledgeIngestService;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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

    private static final Logger log = LoggerFactory.getLogger(KnowledgeDocumentController.class);
    private static final String KIND = "knowledge";

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
        String filename = file.getOriginalFilename() == null ? "unknown" : file.getOriginalFilename();
        log.info(IngestFlowLog.msg(
                KIND,
                "01.recv",
                "userId=" + user.getUserId()
                        + " teamId=" + user.getTeamId()
                        + " filename=\"" + IngestFlowLog.preview(filename) + "\""
                        + " sizeBytes=" + file.getSize()
                        + " title=\"" + IngestFlowLog.preview(title) + "\""));
        // 不打 07.accepted：documentId/jobId/status 与 05.stored 完全重复
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
