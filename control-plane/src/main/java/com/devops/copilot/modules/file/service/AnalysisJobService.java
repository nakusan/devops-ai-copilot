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

        // 校验通过不单独打日志：userId/sizeBytes/filename 与 01.recv 重复，ext/fileType 并入 05.stored
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

        // 承载 MinIO objectKey 与校验结果，替代原 03.validated / 04.minio_upload / 05.db_pending 三条
        log.info(IngestFlowLog.msg(
                KIND,
                "05.stored",
                "jobId=" + jobId
                        + " objectKey=" + objectKey
                        + " ext=" + ext
                        + " fileType=" + fileType.name()
                        + " sizeBytes=" + file.getSize()
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

    /**
     * 硬删分析任务：DB 行 + MinIO 源文件 + 结果 JSON。
     *
     * <p>{@code analysis_jobs} 没有任何指向它的外键，一条 DELETE 即可，无需 CASCADE。
     * 源文件与 result.json 是两个独立对象，都要清；{@code resultObjectKey} 在
     * 未跑完或失败时为 null，由 {@code removeQuietly} 内部忽略。
     *
     * <p>与知识库文档同理，PENDING/PROCESSING 拒绝删除，避免与 worker 回调竞争。
     */
    public void delete(UUID jobId, Long userId) {
        AnalysisJob job = requireOwned(jobId, userId);
        if (!JobStatus.isTerminal(job.getStatus())) {
            throw new BizException(ErrorCode.CONFLICT, "分析任务正在处理中，请等待处理结束后再删除");
        }
        if (analysisJobMapper.deleteById(jobId) == 0) {
            // 并发重复删除：已被另一请求删掉，按幂等处理
            return;
        }
        boolean sourceRemoved = fileStorageService.removeQuietly(job.getObjectKey(), KIND);
        boolean resultRemoved = fileStorageService.removeQuietly(job.getResultObjectKey(), KIND);
        log.info(IngestFlowLog.msg(
                KIND,
                "20.deleted",
                "jobId=" + jobId
                        + " objectKey=" + job.getObjectKey()
                        + " prevStatus=" + job.getStatus()
                        + " sourceRemoved=" + sourceRemoved
                        + " resultRemoved=" + resultRemoved));
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
            // 原 16.status_patch + 17.end 是同一次变迁的两条日志，字段全重；
            // 合成一条，终态 FAILED 时升级为 WARN 保留告警能力。
            String message = IngestFlowLog.msg(
                    KIND,
                    "16.status",
                    "jobId=" + jobId
                            + " " + oldStatus + "→" + req.getStatus()
                            + (req.getResultSummary() != null
                                    ? " summary=\"" + IngestFlowLog.preview(req.getResultSummary()) + "\""
                                    : "")
                            + (req.getErrorMessage() != null
                                    ? " error=\"" + IngestFlowLog.preview(req.getErrorMessage()) + "\""
                                    : ""));
            if (JobStatus.FAILED.name().equals(req.getStatus())) {
                log.warn(message);
            } else {
                log.info(message);
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
