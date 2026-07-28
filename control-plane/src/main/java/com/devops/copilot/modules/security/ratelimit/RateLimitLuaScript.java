package com.devops.copilot.modules.security.ratelimit;

import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.scripting.support.ResourceScriptSource;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;

/**
 * 封装限流 Lua 脚本执行。
 *
 * <p>为何用 Lua：INCR + EXPIRE 分两步会有竞态；脚本在 Redis 单线程内原子完成「补充令牌 + 扣减」。
 */
@Component
public class RateLimitLuaScript {

    private final StringRedisTemplate redisTemplate;
    private final DefaultRedisScript<Long> script;

    public RateLimitLuaScript(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
        this.script = new DefaultRedisScript<>();
        this.script.setResultType(Long.class);
        this.script.setScriptSource(new ResourceScriptSource(new ClassPathResource("lua/rate_limit.lua")));
    }

    /**
     * @param key      Redis key，如 ratelimit:user:1
     * @param capacity 桶容量（≈ 每分钟限额）
     * @return true 表示允许通过
     */
    public boolean tryAcquire(String key, int capacity) {
        long nowMs = System.currentTimeMillis();
        // 每毫秒补充量 = capacity / 60000，使满桶约 1 分钟补满
        double refillPerMs = capacity / 60_000.0;
        List<String> keys = Collections.singletonList(key);
        Long result = redisTemplate.execute(
                script,
                keys,
                String.valueOf(nowMs),
                String.valueOf(capacity),
                String.valueOf(refillPerMs),
                "1");
        return result != null && result == 1L;
    }
}
