package com.devops.copilot.modules.conversation.service;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.conversation.domain.entity.Team;
import com.devops.copilot.modules.conversation.mapper.TeamMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;

/**
 * 团队日 Token 配额服务。
 *
 * <p><b>本阶段不挂 HTTP Filter / Chat 入口</b>：由 Week 5 {@code ChatService} 在发往 LLM 前调用
 * {@link #assertWithinQuota(Long, long)}，流结束后调用 {@link #increaseUsage(Long, long)}。
 *
 * <p>Key：{@code quota:team:{teamId}:daily_tokens}；上限读 {@code teams.daily_token_limit}。
 */
@Service
public class QuotaService {

    private static final Logger log = LoggerFactory.getLogger(QuotaService.class);

    private final StringRedisTemplate redisTemplate;
    private final TeamMapper teamMapper;
    private final Duration keyTtl;

    public QuotaService(
            StringRedisTemplate redisTemplate,
            TeamMapper teamMapper,
            @Value("${copilot.quota.redis-key-ttl:24h}") Duration keyTtl) {
        this.redisTemplate = redisTemplate;
        this.teamMapper = teamMapper;
        this.keyTtl = keyTtl;
    }

    /**
     * 聊天前预检：当前用量 + 本次估算是否超过日限额。
     *
     * @param estimatedTokens 本次 prompt 估算消耗（可粗略）；未知时可传 0 仅检查是否已超限
     */
    public void assertWithinQuota(Long teamId, long estimatedTokens) {
        long limit = resolveDailyLimit(teamId);
        long used = currentUsage(teamId);
        if (used + estimatedTokens > limit) {
            log.warn(
                    "[CHAT] step=02.配额校验 status=exceeded teamId={} used={} estimate={} limit={}",
                    teamId,
                    used,
                    estimatedTokens,
                    limit);
            throw new BizException(ErrorCode.QUOTA_EXCEEDED);
        }
        log.info(
                "[CHAT] step=02.配额校验 status=ok teamId={} used={} estimate={} limit={} remain={}",
                teamId,
                used,
                estimatedTokens,
                limit,
                limit - used);
    }

    /**
     * 聊天成功后累加实际 usage（来自 LLM 返回的 prompt+completion tokens）。
     */
    public void increaseUsage(Long teamId, long actualTokens) {
        if (actualTokens <= 0) {
            return;
        }
        String key = redisKey(teamId);
        Long after = redisTemplate.opsForValue().increment(key, actualTokens);
        // 首次写入时设置 TTL；简化为滚动 24h，而非严格自然日（MVP 可接受）
        if (after != null && after.equals(actualTokens)) {
            redisTemplate.expire(key, keyTtl);
        }
        log.info("[CHAT] step=07.配额累加 teamId={} delta={} after={}", teamId, actualTokens, after);
    }

    public long currentUsage(Long teamId) {
        String raw = redisTemplate.opsForValue().get(redisKey(teamId));
        if (raw == null || raw.isBlank()) {
            return 0L;
        }
        try {
            return Long.parseLong(raw);
        } catch (NumberFormatException ex) {
            log.warn("配额计数损坏，重置为 0: key={}", redisKey(teamId));
            return 0L;
        }
    }

    private long resolveDailyLimit(Long teamId) {
        Team team = teamMapper.selectById(teamId);
        if (team == null || team.getDailyTokenLimit() == null) {
            // 找不到团队时保守拒绝，避免无限制刷模型
            throw new BizException(ErrorCode.NOT_FOUND, "研发组不存在，无法校验配额");
        }
        return team.getDailyTokenLimit();
    }

    static String redisKey(Long teamId) {
        return "quota:team:" + teamId + ":daily_tokens";
    }
}
