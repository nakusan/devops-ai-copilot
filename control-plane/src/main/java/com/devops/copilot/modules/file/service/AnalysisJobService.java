package com.devops.copilot.modules.file.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.common.trace.TraceIds;
import com.devops.copilot.modules.file.controller.dto.AnalysisJobResponse;
import com.devops.copilot.modules.file.controller.dto.UpdateAnalysisJobRequest;
import com.devops.copilot.modules.file.domain.entity.AnalysisJob;
import com.devops.copilot.modules.file.domain.enums.AnalysisFileType;
import com.devops.copilot.modules.file.domain.enums.JobStatus;
import com.devops.copilot.modules.file.kafka.IngestEventProducer;
import com.devops.copilot.modules.file.kafka.event.AnalysisIngestEvent;
import com.devops.copilot.modules.file.logging.IngestFlowLog;
import com.devops.copilot.modules.file.mapper.AnalysisJobMapper;
import com.devops.copilot.modules.conversation.controller.dto.PageResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

/**
 * 大文件分析任务：上传 MinIO → 落库 → 发 Kafka → 202。
 */
@Service
public class AnalysisJobService {

    private static final Logger log = LoggerFactory.getLogger(AnalysisJobService.class);
    private static final String KIND = "analysis";

    private static final Map<String, AnalysisFileType> EXT_TO_TYPE = Map.of(
            "hprof", AnalysisFileType.HEAP_DUMP,
            "log", AnalysisFileType.APP_LOG,
            "txt", AnalysisFileType.APP_LOG);

    private final AnalysisJobMapper analysisJobMapper;
    private final FileStorageService fileStorageService;
    private final UploadPolicyService uploadPolicyService;
    private final IngestEventProducer ingestEventProducer;

    public AnalysisJobService(
            AnalysisJobMapper analysisJobMapper,
            FileStorageService fileStorageService,
            UploadPolicyService uploadPolicyService,
            IngestEventProducer ingestEventProducer) {
        this.analysisJobMapper = analysisJobMapper;
        this.fileStorageService = fileStorageService;
        this.uploadPolicyService = uploadPolicyService;
        this.ingestEventProducer = ingestEventProducer;
    }

    @Transactional
    public AnalysisJobResponse create(
            MultipartFile file, Long userId, Long teamId, AnalysisFileType fileTypeOverride) {
        uploadPolicyService.checkUploadRateLimit(userId, KIND);
        String filename = file.getOriginalFilename() == null ? "upload.bin" : file.getOriginalFilename();
        String ext = uploadPolicyService.validateAnalysisUpload(filename, file.getSize());

        AnalysisFileType fileType = fileTypeOverride != null
                ? fileTypeOverride
                : EXT_TO_TYPE.getOrDefault(ext, AnalysisFileType.APP_LOG);

        log.info(IngestFlowLog.msg(
                KIND,
                "03.validated",
                "userId=" + userId
                        + " ext=" + ext
                        + " fileType=" + fileType.name()
                        + " sizeBytes=" + file.getSize()
                        + " filename=\"" + IngestFlowLog.preview(filename) + "\""));

        UUID jobId = UUID.randomUUID();
        String objectKey = "analysis/" + jobId + "/source." + ext;
        OffsetDateTime now = OffsetDateTime.now();

        try (InputStream in = file.getInputStream()) {
            fileStorageService.uploadStream(objectKey, in, file.getSize(), file.getContentType(), KIND);
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new BizException(ErrorCode.STORAGE_ERROR, "读取上传流失败");
        }

        AnalysisJob job = new AnalysisJob();
        job.setId(jobId);
        job.setUserId(userId);
        job.setObjectKey(objectKey);
        job.setFileType(fileType.name());
        job.setStatus(JobStatus.PENDING.name());
        job.setRetryCount(0);
        job.setCreatedAt(now);
        job.setUpdatedAt(now);
        analysisJobMapper.insert(job);

        log.info(IngestFlowLog.msg(
                KIND,
                "05.db_pending",
                "jobId=" + jobId
                        + " objectKey=" + objectKey
                        + " fileType=" + fileType.name()
                        + " status=PENDING"));

        AnalysisIngestEvent event = new AnalysisIngestEvent();
        event.setEventId(UUID.randomUUID());
        event.setJobId(jobId);
        event.setUserId(userId);
        event.setTeamId(teamId);
        event.setObjectKey(objectKey);
        event.setFileType(fileType.name());
        event.setTraceId(TraceIds.current());
        event.setCreatedAt(now);

        try {
            ingestEventProducer.publishAnalysisIngest(event);
        } catch (RuntimeException ex) {
            job.setStatus(JobStatus.FAILED.name());
            job.setErrorMessage("KAFKA_PUBLISH_FAILED");
            job.setUpdatedAt(OffsetDateTime.now());
            analysisJobMapper.updateById(job);
            log.warn(IngestFlowLog.msg(
                    KIND,
                    "08.kafka_fail",
                    "jobId=" + jobId + " error=\"KAFKA_PUBLISH_FAILED\""));
            throw new BizException(ErrorCode.INGEST_PUBLISH_FAILED);
        }

        return toResponse(job);
    }

    public AnalysisJobResponse getMine(UUID jobId, Long userId) {
        return toResponse(requireOwned(jobId, userId));
    }

    public PageResponse<AnalysisJobResponse> listMine(Long userId, long page, long size) {
        Page<AnalysisJob> p = analysisJobMapper.selectPage(
                new Page<>(page, size),
                new LambdaQueryWrapper<AnalysisJob>()
                        .eq(AnalysisJob::getUserId, userId)
                        .orderByDesc(AnalysisJob::getCreatedAt));
        return new PageResponse<>(
                p.getRecords().stream().map(this::toResponse).toList(),
                p.getTotal(),
                page,
                size);
    }

    /**
     * Internal：按 userId 取最近一次 COMPLETED（LangGraph AnalysisLookupNode）。
     */
    public AnalysisJobResponse getLatestCompleted(Long userId) {
        AnalysisJob job = analysisJobMapper.selectOne(new LambdaQueryWrapper<AnalysisJob>()
                .eq(AnalysisJob::getUserId, userId)
                .eq(AnalysisJob::getStatus, JobStatus.COMPLETED.name())
                .orderByDesc(AnalysisJob::getUpdatedAt)
                .last("LIMIT 1"));
        return job == null ? null : toResponse(job);
    }

    public AnalysisJobResponse getInternal(UUID jobId) {
        AnalysisJob job = analysisJobMapper.selectById(jobId);
        if (job == null) {
            throw new BizException(ErrorCode.NOT_FOUND, "分析任务不存在");
        }
        return toResponse(job);
    }

    @Transactional
    public AnalysisJobResponse patchInternal(UUID jobId, UpdateAnalysisJobRequest req) {
        AnalysisJob job = analysisJobMapper.selectById(jobId);
        if (job == null) {
            throw new BizException(ErrorCode.NOT_FOUND, "分析任务不存在");
        }
        String oldStatus = job.getStatus();
        if (req.getStatus() != null) {
            validateStatus(req.getStatus());
            job.setStatus(req.getStatus());
        }
        if (req.getResultSummary() != null) {
            String summary = req.getResultSummary();
            if (summary.length() > 2048) {
                summary = summary.substring(0, 2048);
            }
            job.setResultSummary(summary);
        }
        if (req.getResultObjectKey() != null) {
            job.setResultObjectKey(req.getResultObjectKey());
        }
        if (req.getErrorMessage() != null) {
            job.setErrorMessage(truncate(req.getErrorMessage(), 500));
        }
        if (req.getRetryCount() != null) {
            job.setRetryCount(req.getRetryCount());
        }
        job.setUpdatedAt(OffsetDateTime.now());
        analysisJobMapper.updateById(job);

        if (req.getStatus() != null && !req.getStatus().equals(oldStatus)) {
            log.info(IngestFlowLog.msg(
                    KIND,
                    "16.status_patch",
                    "jobId=" + jobId
                            + " " + oldStatus + "→" + req.getStatus()
                            + (req.getResultSummary() != null
                                    ? " summary=\"" + IngestFlowLog.preview(req.getResultSummary()) + "\""
                                    : "")
                            + (req.getErrorMessage() != null
                                    ? " error=\"" + IngestFlowLog.preview(req.getErrorMessage()) + "\""
                                    : "")));
            if (JobStatus.COMPLETED.name().equals(req.getStatus())) {
                log.info(IngestFlowLog.msg(
                        KIND,
                        "17.end",
                        "jobId=" + jobId
                                + " status=COMPLETED"
                                + " summary=\"" + IngestFlowLog.preview(job.getResultSummary()) + "\""));
            } else if (JobStatus.FAILED.name().equals(req.getStatus())) {
                log.warn(IngestFlowLog.msg(
                        KIND,
                        "17.end",
                        "jobId=" + jobId + " status=FAILED error=\"" + IngestFlowLog.preview(job.getErrorMessage()) + "\""));
            }
        }

        return toResponse(job);
    }

    private AnalysisJob requireOwned(UUID jobId, Long userId) {
        AnalysisJob job = analysisJobMapper.selectById(jobId);
        if (job == null) {
            throw new BizException(ErrorCode.NOT_FOUND, "分析任务不存在");
        }
        if (!job.getUserId().equals(userId)) {
            throw new BizException(ErrorCode.FORBIDDEN);
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

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max);
    }

    private AnalysisJobResponse toResponse(AnalysisJob job) {
        return new AnalysisJobResponse(
                job.getId(),
                job.getFileType(),
                job.getStatus(),
                job.getResultSummary(),
                job.getErrorMessage(),
                job.getCreatedAt(),
                job.getUpdatedAt());
    }
}
