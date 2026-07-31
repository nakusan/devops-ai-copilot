package com.devops.copilot.modules.file.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

/**
 * 上传策略：扩展名白名单与大小上限（设计 6.3 §3.4 / §8）。
 */
@ConfigurationProperties(prefix = "copilot.file")
public class FileProperties {

    private final Knowledge knowledge = new Knowledge();
    private final Analysis analysis = new Analysis();
    private int uploadRateLimitPerHour = 10;

    public Knowledge getKnowledge() {
        return knowledge;
    }

    public Analysis getAnalysis() {
        return analysis;
    }

    public int getUploadRateLimitPerHour() {
        return uploadRateLimitPerHour;
    }

    public void setUploadRateLimitPerHour(int uploadRateLimitPerHour) {
        this.uploadRateLimitPerHour = uploadRateLimitPerHour;
    }

    public static class Knowledge {
        private long maxBytes = 20L * 1024 * 1024;
        private List<String> allowedExtensions = new ArrayList<>(List.of("pdf", "md", "txt"));

        public long getMaxBytes() {
            return maxBytes;
        }

        public void setMaxBytes(long maxBytes) {
            this.maxBytes = maxBytes;
        }

        public List<String> getAllowedExtensions() {
            return allowedExtensions;
        }

        public void setAllowedExtensions(List<String> allowedExtensions) {
            this.allowedExtensions = allowedExtensions;
        }
    }

    public static class Analysis {
        private long maxBytes = 100L * 1024 * 1024;
        private List<String> allowedExtensions = new ArrayList<>(List.of("log", "txt", "hprof"));

        public long getMaxBytes() {
            return maxBytes;
        }

        public void setMaxBytes(long maxBytes) {
            this.maxBytes = maxBytes;
        }

        public List<String> getAllowedExtensions() {
            return allowedExtensions;
        }

        public void setAllowedExtensions(List<String> allowedExtensions) {
            this.allowedExtensions = allowedExtensions;
        }
    }
}
