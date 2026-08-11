package com.devops.copilot.modules.security.filter;

import com.devops.copilot.common.api.ErrorResponse;
import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.common.trace.TraceIds;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import com.devops.copilot.modules.security.jwt.JwtTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 用户 JWT 校验 Filter。
 *
 * <p>公开路径与 /internal/** 跳过：前者无需登录，后者走 ServiceTokenFilter。
 *
 * <p>SSE（SseEmitter）结束时 Tomcat 会做 async dispatch；OncePerRequestFilter 默认跳过异步派发，
 * 会导致 SecurityContext 丢失并触发误报 AccessDenied。因此本 Filter 在 async/error dispatch 也执行。
 */
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenProvider jwtTokenProvider;
    private final ObjectMapper objectMapper;

    public JwtAuthenticationFilter(JwtTokenProvider jwtTokenProvider, ObjectMapper objectMapper) {
        this.jwtTokenProvider = jwtTokenProvider;
        this.objectMapper = objectMapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path.startsWith("/internal/")
                || path.startsWith("/actuator/")
                || path.startsWith("/api/v1/auth/");
    }

    /** SSE complete 等异步收尾时也要恢复 JWT，避免匿名 AccessDenied。 */
    @Override
    protected boolean shouldNotFilterAsyncDispatch() {
        return false;
    }

    /** 错误页派发时同样尝试恢复身份，减少 /error 连锁鉴权失败。 */
    @Override
    protected boolean shouldNotFilterErrorDispatch() {
        return false;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            // 交给后续 AuthorizationFilter 返回 401；此处不提前写响应，保持职责单一
            filterChain.doFilter(request, response);
            return;
        }

        String token = header.substring(7);
        try {
            UserPrincipal principal = jwtTokenProvider.parseAccessToken(token);
            var authentication = new UsernamePasswordAuthenticationToken(
                    principal, null, principal.getAuthorities());
            SecurityContextHolder.getContext().setAuthentication(authentication);
            filterChain.doFilter(request, response);
        } catch (BizException ex) {
            SecurityContextHolder.clearContext();
            // SSE 已写出时响应已 committed，无法再写 401；继续链以免二次破坏连接
            if (response.isCommitted()) {
                filterChain.doFilter(request, response);
                return;
            }
            writeError(response, ex.getErrorCode(), ex.getMessage());
        }
    }

    private void writeError(HttpServletResponse response, ErrorCode code, String message) throws IOException {
        response.setStatus(code.getStatus().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        objectMapper.writeValue(
                response.getOutputStream(),
                ErrorResponse.of(code.getCode(), message, TraceIds.current()));
    }
}
