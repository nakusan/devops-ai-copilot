package com.devops.copilot.modules.security.filter;

import com.devops.copilot.common.api.ErrorResponse;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.common.trace.TraceIds;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import com.devops.copilot.modules.security.ratelimit.RateLimitLuaScript;
import com.devops.copilot.modules.security.ratelimit.RateLimitProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 用户级 + IP 级限流。必须放在 JwtAuthenticationFilter 之后，才能读到 UserPrincipal。
 *
 * <p>公开路径与 /internal 跳过：登录本身也需防刷时，可另加 IP 限流到 auth；MVP 先保持简单。
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    private final RateLimitLuaScript rateLimitLuaScript;
    private final RateLimitProperties properties;
    private final ObjectMapper objectMapper;

    public RateLimitFilter(
            RateLimitLuaScript rateLimitLuaScript,
            RateLimitProperties properties,
            ObjectMapper objectMapper) {
        this.rateLimitLuaScript = rateLimitLuaScript;
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path.startsWith("/api/v1/auth/")
                || path.startsWith("/actuator/")
                || path.startsWith("/internal/");
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String ip = clientIp(request);
        if (!rateLimitLuaScript.tryAcquire("ratelimit:ip:" + ip, properties.getIpPerMinute())) {
            writeLimited(response);
            return;
        }

        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof UserPrincipal principal) {
            String userKey = "ratelimit:user:" + principal.getUserId();
            if (!rateLimitLuaScript.tryAcquire(userKey, properties.getUserPerMinute())) {
                writeLimited(response);
                return;
            }
        }

        filterChain.doFilter(request, response);
    }

    /**
     * 优先 X-Forwarded-For（前置反向代理场景）；无则用 remoteAddr。
     * 生产需确保只信任可信代理写入的头，否则客户端可伪造 IP 绕过/嫁祸。
     */
    private static String clientIp(HttpServletRequest request) {
        String xff = request.getHeader("X-Forwarded-For");
        if (xff != null && !xff.isBlank()) {
            return xff.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    private void writeLimited(HttpServletResponse response) throws IOException {
        response.setStatus(ErrorCode.RATE_LIMITED.getStatus().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        objectMapper.writeValue(
                response.getOutputStream(),
                ErrorResponse.of(
                        ErrorCode.RATE_LIMITED.getCode(),
                        ErrorCode.RATE_LIMITED.getDefaultMessage(),
                        TraceIds.current()));
    }
}
