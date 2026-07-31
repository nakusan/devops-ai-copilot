package com.devops.copilot.modules.file.controller.internal;

import com.devops.copilot.modules.file.controller.dto.ChunkBatchRequest;
import com.devops.copilot.modules.file.controller.dto.IngestJobResponse;
import com.devops.copilot.modules.file.controller.dto.UpdateIngestJobRequest;
import com.devops.copilot.modules.file.service.IngestJobService;
import com.devops.copilot.modules.file.service.KnowledgeChunkService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.UUID;

/**
 * Python Knowledge Ingest Worker 回调入口。
 */
@RestController
@RequestMapping("/internal/v1")
public class InternalIngestController {

    private final IngestJobService ingestJobService;
    private final KnowledgeChunkService knowledgeChunkService;

    public InternalIngestController(
            IngestJobService ingestJobService, KnowledgeChunkService knowledgeChunkService) {
        this.ingestJobService = ingestJobService;
        this.knowledgeChunkService = knowledgeChunkService;
    }

    @GetMapping("/ingest-jobs/{id}")
    public IngestJobResponse getJob(@PathVariable("id") UUID id) {
        return ingestJobService.get(id);
    }

    @PatchMapping("/ingest-jobs/{id}")
    public IngestJobResponse patchJob(
            @PathVariable("id") UUID id, @RequestBody UpdateIngestJobRequest request) {
        return ingestJobService.updateStatus(id, request);
    }

    @PostMapping("/knowledge/chunks/batch")
    public Map<String, Object> batchChunks(@Valid @RequestBody ChunkBatchRequest request) {
        int count = knowledgeChunkService.batchInsert(request);
        return Map.of("inserted", count, "documentId", request.getDocumentId());
    }
}
