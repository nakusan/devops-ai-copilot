package com.devops.copilot.modules.file.controller.internal;

import com.devops.copilot.modules.file.controller.dto.AnalysisJobResponse;
import com.devops.copilot.modules.file.controller.dto.UpdateAnalysisJobRequest;
import com.devops.copilot.modules.file.service.AnalysisJobService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

/**
 * Python Analysis Worker / Agent 回调入口（Service Token 保护）。
 */
@RestController
@RequestMapping("/internal/v1/analysis-jobs")
public class InternalAnalysisJobController {

    private final AnalysisJobService analysisJobService;

    public InternalAnalysisJobController(AnalysisJobService analysisJobService) {
        this.analysisJobService = analysisJobService;
    }

    @GetMapping("/{id}")
    public AnalysisJobResponse get(@PathVariable("id") UUID id) {
        return analysisJobService.getInternal(id);
    }

    /**
     * {@code latest=true}：最近一次 COMPLETED（兼容旧 AnalysisLookup）；无结果 204。
     * {@code latest=false}：最近 {@code limit} 条任务列表（Agent list_analysis_jobs）。
     */
    @GetMapping
    public ResponseEntity<?> query(
            @RequestParam Long userId,
            @RequestParam(defaultValue = "COMPLETED") String status,
            @RequestParam(defaultValue = "true") boolean latest,
            @RequestParam(defaultValue = "5") int limit) {
        if (latest) {
            // status 保留契约兼容；当前 latest 仍只取 COMPLETED
            AnalysisJobResponse job = analysisJobService.getLatestCompleted(userId);
            return job == null ? ResponseEntity.noContent().build() : ResponseEntity.ok(job);
        }
        List<AnalysisJobResponse> jobs = analysisJobService.listRecent(userId, limit);
        return ResponseEntity.ok(jobs);
    }

    @PatchMapping("/{id}")
    public AnalysisJobResponse patch(
            @PathVariable("id") UUID id, @RequestBody UpdateAnalysisJobRequest request) {
        return analysisJobService.patchInternal(id, request);
    }
}
