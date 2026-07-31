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

import java.util.UUID;

/**
 * Python Analysis Worker / LangGraph 回调入口（Service Token 保护）。
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
     * 查询用户最近一次已完成分析（AnalysisLookupNode）。
     * 无结果返回 204。
     */
    @GetMapping
    public ResponseEntity<AnalysisJobResponse> latest(
            @RequestParam Long userId,
            @RequestParam(defaultValue = "COMPLETED") String status,
            @RequestParam(defaultValue = "true") boolean latest) {
        // MVP：聊天场景只取最近 COMPLETED；status/latest 保留契约兼容
        if (!latest || !"COMPLETED".equals(status)) {
            // 非 latest 查询 V1 再扩展；当前仍回落最新 COMPLETED
        }
        AnalysisJobResponse job = analysisJobService.getLatestCompleted(userId);
        return job == null ? ResponseEntity.noContent().build() : ResponseEntity.ok(job);
    }

    @PatchMapping("/{id}")
    public AnalysisJobResponse patch(
            @PathVariable("id") UUID id, @RequestBody UpdateAnalysisJobRequest request) {
        return analysisJobService.patchInternal(id, request);
    }
}
