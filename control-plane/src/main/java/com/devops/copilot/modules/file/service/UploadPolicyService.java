package com.devops.copilot.modules.file.service;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.file.config.FileProperties;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.Duration;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 上传校验 + 按用户小时级限流。
 *
 * <p>限流用 INCR+TTL，而非全局分钟令牌桶：上传是低频重操作，按小时配额更贴合设计。
 */
@Service
public class UploadPolicyService {

    private final FileProperties fileProperties;
    private final StringRedisTemplate redisTemplate;

    public UploadPolicyService(FileProperties fileProperties, StringRedisTemplate redisTemplate) {
        this.fileProperties = fileProperties;
        this.redisTemplate = redisTemplate;
    }

    public void checkUploadRateLimit(Long userId) {
        String key = "ratelimit:upload:user:" + userId;
        Long count = redisTemplate.opsForValue().increment(key);
        if (count != null && count == 1L) {
            redisTemplate.expire(key, Duration.ofHours(1));
        }
        int limit = fileProperties.getUploadRateLimitPerHour();
        if (count != null && count > limit) {
            throw new BizException(ErrorCode.RATE_LIMITED, "上传过于频繁，每小时最多 " + limit + " 次");
        }
    }

    public String validateKnowledgeUpload(String filename, long size) {
        String ext = extension(filename);
        Set<String> allowed = toLowerSet(fileProperties.getKnowledge().getAllowedExtensions());
        if (!allowed.contains(ext)) {
            throw new BizException(ErrorCode.UNSUPPORTED_FILE_TYPE, "知识库仅支持: " + allowed);
        }
        if (size > fileProperties.getKnowledge().getMaxBytes()) {
            throw new BizException(ErrorCode.FILE_TOO_LARGE, "知识库文件不能超过 20MB");
        }
        return ext;
    }

    public String validateAnalysisUpload(String filename, long size) {
        String ext = extension(filename);
        Set<String> allowed = toLowerSet(fileProperties.getAnalysis().getAllowedExtensions());
        if (!allowed.contains(ext)) {
            throw new BizException(ErrorCode.UNSUPPORTED_FILE_TYPE, "分析文件仅支持: " + allowed);
        }
        if (size > fileProperties.getAnalysis().getMaxBytes()) {
            throw new BizException(ErrorCode.FILE_TOO_LARGE, "分析文件不能超过 100MB");
        }
        return ext;
    }

    public static String extension(String filename) {
        if (!StringUtils.hasText(filename) || !filename.contains(".")) {
            throw new BizException(ErrorCode.UNSUPPORTED_FILE_TYPE, "文件名缺少扩展名");
        }
        return filename.substring(filename.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }

    private static Set<String> toLowerSet(java.util.List<String> list) {
        return list.stream().map(s -> s.toLowerCase(Locale.ROOT)).collect(Collectors.toSet());
    }
}
