package com.devops.copilot.modules.file.service;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.file.controller.dto.IngestJobResponse;
import com.devops.copilot.modules.file.controller.dto.UpdateIngestJobRequest;
import com.devops.copilot.modules.file.domain.entity.IngestJob;
import com.devops.copilot.modules.file.domain.entity.KnowledgeDocument;
import com.devops.copilot.modules.file.domain.enums.JobStatus;
import com.devops.copilot.modules.file.logging.IngestFlowLog;
import com.devops.copilot.modules.file.mapper.IngestJobMapper;
import com.devops.copilot.modules.file.mapper.KnowledgeDocumentMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * ingest_jobs 状态更新；同步镜像到 knowledge_documents.status。
 */
@Service
public class IngestJobService {

    private static final Logger log = LoggerFactory.getLogger(IngestJobService.class);
    private static final String KIND = "knowledge";

    private final IngestJobMapper ingestJobMapper;
    private final KnowledgeDocumentMapper documentMapper;

    public IngestJobService(IngestJobMapper ingestJobMapper, KnowledgeDocumentMapper documentMapper) {
        this.ingestJobMapper = ingestJobMapper;
        this.documentMapper = documentMapper;
    }

    public IngestJobResponse get(UUID jobId) {
        return toResponse(requireJob(jobId));
    }

    @Transactional
    public IngestJobResponse updateStatus(UUID jobId, UpdateIngestJobRequest req) {
        IngestJob job = requireJob(jobId);
        String oldStatus = job.getStatus();
        if (req.getStatus() != null) {
            validateStatus(req.getStatus());
            if (JobStatus.COMPLETED.name().equals(job.getStatus())
                    && !JobStatus.COMPLETED.name().equals(req.getStatus())) {
                return toResponse(job);
            }
            job.setStatus(req.getStatus());
        }
        if (req.getErrorMessage() != null) {
            String err = req.getErrorMessage();
            job.setErrorMessage(err.length() > 500 ? err.substring(0, 500) : err);
        }
        if (req.getRetryCount() != null) {
            job.setRetryCount(req.getRetryCount());
        }
        job.setUpdatedAt(OffsetDateTime.now());
        ingestJobMapper.updateById(job);

        KnowledgeDocument doc = documentMapper.selectById(job.getDocumentId());
        if (doc != null && req.getStatus() != null) {
            doc.setStatus(req.getStatus());
            doc.setErrorMessage(job.getErrorMessage());
            doc.setUpdatedAt(OffsetDateTime.now());
            documentMapper.updateById(doc);
        }

        if (req.getStatus() != null && !req.getStatus().equals(oldStatus)) {
            // 原 16.status_patch + 17.end 是同一次变迁的两条日志，字段全重；
            // 合成一条，终态 FAILED 时升级为 WARN 保留告警能力。
            String message = IngestFlowLog.msg(
                    KIND,
                    "16.status",
                    "jobId=" + jobId
                            + " documentId=" + job.getDocumentId()
                            + " " + oldStatus + "→" + req.getStatus()
                            + (job.getErrorMessage() != null
                                    ? " error=\"" + IngestFlowLog.preview(job.getErrorMessage()) + "\""
                                    : ""));
            if (JobStatus.FAILED.name().equals(req.getStatus())) {
                log.warn(message);
            } else {
                log.info(message);
            }
        }

        return toResponse(job);
    }

    private IngestJob requireJob(UUID jobId) {
        IngestJob job = ingestJobMapper.selectById(jobId);
        if (job == null) {
            throw new BizException(ErrorCode.NOT_FOUND, "入库任务不存在");
        }
        return job;
    }

    private static void validateStatus(String status) {
        try {
            JobStatus.valueOf(status);
        } catch (IllegalArgumentException ex) {
            throw new BizException(ErrorCode.VALIDATION_ERROR, "非法 status: " + status);
        }
    }

    private IngestJobResponse toResponse(IngestJob job) {
        return new IngestJobResponse(
                job.getId(),
                job.getDocumentId(),
                job.getStatus(),
                job.getRetryCount(),
                job.getErrorMessage(),
                job.getKafkaOffset(),
                job.getCreatedAt(),
                job.getUpdatedAt());
    }
}
