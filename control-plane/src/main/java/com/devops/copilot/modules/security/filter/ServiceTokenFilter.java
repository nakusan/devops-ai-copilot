package com.devops.copilot.modules.security.filter;

import com.devops.copilot.common.api.ErrorResponse;
import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.common.trace.TraceIds;
import com.devops.copilot.modules.security.jwt.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 保护 /internal/**：只接受 Service Token，不走用户 JWT。
 *
 * <p>Phase 1 尚无内部业务 API，但提前挂 Filter，避免后续误开裸接口。
 */
@Component
public class ServiceTokenFilter extends OncePerRequestFilter {

    private final ServiceTokenProvider serviceTokenProvider;
    private final ObjectMapper objectMapper;

    public ServiceTokenFilter(ServiceTokenProvider serviceTokenProvider, ObjectMapper objectMapper) {
        this.serviceTokenProvider = serviceTokenProvider;
        this.objectMapper = objectMapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/internal/");
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String token = request.getHeader(ServiceTokenProvider.HEADER);
        if (token == null || token.isBlank()) {
            writeError(response, ErrorCode.AUTH_INVALID, "缺少 X-Service-Token");
            return;
        }
        try {
            serviceTokenProvider.verify(token);
            filterChain.doFilter(request, response);
        } catch (BizException ex) {
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
