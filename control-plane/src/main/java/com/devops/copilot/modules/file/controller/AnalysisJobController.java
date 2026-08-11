package com.devops.copilot.modules.file.controller;

import com.devops.copilot.common.security.SecurityUtils;
import com.devops.copilot.modules.conversation.controller.dto.PageResponse;
import com.devops.copilot.modules.file.controller.dto.AnalysisJobResponse;
import com.devops.copilot.modules.file.domain.enums.AnalysisFileType;
import com.devops.copilot.modules.file.logging.IngestFlowLog;
import com.devops.copilot.modules.file.service.AnalysisJobService;
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
@RequestMapping("/api/v1/analysis/jobs")
public class AnalysisJobController {

    private static final Logger log = LoggerFactory.getLogger(AnalysisJobController.class);
    private static final String KIND = "analysis";

    private final AnalysisJobService analysisJobService;

    public AnalysisJobController(AnalysisJobService analysisJobService) {
        this.analysisJobService = analysisJobService;
    }

    /**
     * 上传 heap/log → MinIO → Kafka → 202。
     *
     * @param fileType 可选；不传则按扩展名推断（hprof→HEAP_DUMP，其余→APP_LOG）
     */
    @PostMapping
    @ResponseStatus(HttpStatus.ACCEPTED)
    public AnalysisJobResponse create(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "fileType", required = false) AnalysisFileType fileType) {
        UserPrincipal user = SecurityUtils.currentUser();
        String filename = file.getOriginalFilename() == null ? "unknown" : file.getOriginalFilename();
        log.info(IngestFlowLog.msg(
                KIND,
                "01.recv",
                "userId=" + user.getUserId()
                        + " teamId=" + user.getTeamId()
                        + " filename=\"" + IngestFlowLog.preview(filename) + "\""
                        + " sizeBytes=" + file.getSize()
                        + " fileType=" + (fileType != null ? fileType.name() : "auto")));
        AnalysisJobResponse resp =
                analysisJobService.create(file, user.getUserId(), user.getTeamId(), fileType);
        log.info(IngestFlowLog.msg(
                KIND,
                "07.accepted",
                "jobId=" + resp.jobId() + " status=" + resp.status() + " fileType=" + resp.fileType()));
        return resp;
    }

    @GetMapping("/{id}")
    public AnalysisJobResponse get(@PathVariable("id") UUID id) {
        UserPrincipal user = SecurityUtils.currentUser();
        return analysisJobService.getMine(id, user.getUserId());
    }

    @GetMapping
    public PageResponse<AnalysisJobResponse> list(
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        UserPrincipal user = SecurityUtils.currentUser();
        return analysisJobService.listMine(user.getUserId(), page, size);
    }
}
