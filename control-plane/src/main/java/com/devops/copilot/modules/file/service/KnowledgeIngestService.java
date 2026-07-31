package com.devops.copilot.modules.file.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.common.trace.TraceIds;
import com.devops.copilot.modules.conversation.controller.dto.PageResponse;
import com.devops.copilot.modules.file.controller.dto.IngestResponse;
import com.devops.copilot.modules.file.controller.dto.KnowledgeDocumentResponse;
import com.devops.copilot.modules.file.domain.entity.IngestJob;
import com.devops.copilot.modules.file.domain.entity.KnowledgeDocument;
import com.devops.copilot.modules.file.domain.enums.JobStatus;
import com.devops.copilot.modules.file.kafka.IngestEventProducer;
import com.devops.copilot.modules.file.kafka.event.KnowledgeIngestEvent;
import com.devops.copilot.modules.file.mapper.IngestJobMapper;
import com.devops.copilot.modules.file.mapper.KnowledgeDocumentMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.time.OffsetDateTime;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * 知识库文档上传与入库调度（设计 6.3 §3.5）。
 */
@Service
public class KnowledgeIngestService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeIngestService.class);

    private final KnowledgeDocumentMapper documentMapper;
    private final IngestJobMapper ingestJobMapper;
    private final FileStorageService fileStorageService;
    private final UploadPolicyService uploadPolicyService;
    private final IngestEventProducer ingestEventProducer;

    public KnowledgeIngestService(
            KnowledgeDocumentMapper documentMapper,
            IngestJobMapper ingestJobMapper,
            FileStorageService fileStorageService,
            UploadPolicyService uploadPolicyService,
            IngestEventProducer ingestEventProducer) {
        this.documentMapper = documentMapper;
        this.ingestJobMapper = ingestJobMapper;
        this.fileStorageService = fileStorageService;
        this.uploadPolicyService = uploadPolicyService;
        this.ingestEventProducer = ingestEventProducer;
    }

    @Transactional
    public IngestResponse ingest(MultipartFile file, Long userId, Long teamId, String title) {
        uploadPolicyService.checkUploadRateLimit(userId);
        String filename = file.getOriginalFilename() == null ? "document.bin" : file.getOriginalFilename();
        String ext = uploadPolicyService.validateKnowledgeUpload(filename, file.getSize());

        UUID documentId = UUID.randomUUID();
        UUID jobId = UUID.randomUUID();
        String objectKey = "knowledge/" + documentId + "/original." + ext;
        String mimeType = resolveMime(ext, file.getContentType());
        OffsetDateTime now = OffsetDateTime.now();
        String docTitle = (title == null || title.isBlank()) ? filename : title;

        try (InputStream in = file.getInputStream()) {
            fileStorageService.uploadStream(objectKey, in, file.getSize(), mimeType);
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new BizException(ErrorCode.STORAGE_ERROR, "读取上传流失败");
        }

        KnowledgeDocument doc = new KnowledgeDocument();
        doc.setId(documentId);
        doc.setUserId(userId);
        doc.setTeamId(teamId);
        doc.setTitle(docTitle);
        doc.setObjectKey(objectKey);
        doc.setMimeType(mimeType);
        doc.setSizeBytes(file.getSize());
        doc.setStatus(JobStatus.PENDING.name());
        doc.setMetadataJson(Map.of("originalFilename", filename));
        doc.setCreatedAt(now);
        doc.setUpdatedAt(now);
        documentMapper.insert(doc);

        IngestJob job = new IngestJob();
        job.setId(jobId);
        job.setDocumentId(documentId);
        job.setStatus(JobStatus.PENDING.name());
        job.setRetryCount(0);
        job.setCreatedAt(now);
        job.setUpdatedAt(now);
        ingestJobMapper.insert(job);

        KnowledgeIngestEvent event = new KnowledgeIngestEvent();
        event.setEventId(UUID.randomUUID());
        event.setJobId(jobId);
        event.setDocumentId(documentId);
        event.setObjectKey(objectKey);
        event.setMimeType(mimeType);
        event.setUserId(userId);
        event.setTeamId(teamId);
        event.setTraceId(TraceIds.current());
        event.setCreatedAt(now);

        try {
            long offset = ingestEventProducer.publishKnowledgeIngest(event);
            job.setKafkaOffset(offset);
            job.setUpdatedAt(OffsetDateTime.now());
            ingestJobMapper.updateById(job);
        } catch (RuntimeException ex) {
            markFailed(job, doc, "KAFKA_PUBLISH_FAILED");
            throw new BizException(ErrorCode.INGEST_PUBLISH_FAILED);
        }

        log.info("knowledge ingest created documentId={} jobId={} userId={}", documentId, jobId, userId);
        return new IngestResponse(documentId, jobId, JobStatus.PENDING.name());
    }

    public KnowledgeDocumentResponse getMine(UUID documentId, Long userId) {
        return toDocResponse(requireOwnedDoc(documentId, userId));
    }

    public PageResponse<KnowledgeDocumentResponse> listMine(Long userId, long page, long size) {
        Page<KnowledgeDocument> p = documentMapper.selectPage(
                new Page<>(page, size),
                new LambdaQueryWrapper<KnowledgeDocument>()
                        .eq(KnowledgeDocument::getUserId, userId)
                        .orderByDesc(KnowledgeDocument::getCreatedAt));
        return new PageResponse<>(
                p.getRecords().stream().map(this::toDocResponse).toList(),
                p.getTotal(),
                page,
                size);
    }

    public KnowledgeDocument requireExists(UUID documentId) {
        KnowledgeDocument doc = documentMapper.selectById(documentId);
        if (doc == null) {
            throw new BizException(ErrorCode.NOT_FOUND, "文档不存在");
        }
        return doc;
    }

    private KnowledgeDocument requireOwnedDoc(UUID documentId, Long userId) {
        KnowledgeDocument doc = requireExists(documentId);
        if (!doc.getUserId().equals(userId)) {
            throw new BizException(ErrorCode.FORBIDDEN);
        }
        return doc;
    }

    private void markFailed(IngestJob job, KnowledgeDocument doc, String error) {
        OffsetDateTime now = OffsetDateTime.now();
        job.setStatus(JobStatus.FAILED.name());
        job.setErrorMessage(error);
        job.setUpdatedAt(now);
        ingestJobMapper.updateById(job);
        doc.setStatus(JobStatus.FAILED.name());
        doc.setErrorMessage(error);
        doc.setUpdatedAt(now);
        documentMapper.updateById(doc);
    }

    private static String resolveMime(String ext, String contentType) {
        if (contentType != null && !contentType.isBlank()) {
            return contentType;
        }
        return switch (ext.toLowerCase(Locale.ROOT)) {
            case "pdf" -> "application/pdf";
            case "md" -> "text/markdown";
            case "txt" -> "text/plain";
            default -> "application/octet-stream";
        };
    }

    private KnowledgeDocumentResponse toDocResponse(KnowledgeDocument doc) {
        return new KnowledgeDocumentResponse(
                doc.getId(),
                doc.getTitle(),
                doc.getMimeType(),
                doc.getSizeBytes(),
                doc.getStatus(),
                doc.getErrorMessage(),
                doc.getCreatedAt(),
                doc.getUpdatedAt());
    }
}
