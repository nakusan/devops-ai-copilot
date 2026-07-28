package com.devops.copilot.modules.security.config;

import com.devops.copilot.common.api.ErrorResponse;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.common.trace.TraceIds;
import com.devops.copilot.modules.security.filter.JwtAuthenticationFilter;
import com.devops.copilot.modules.security.filter.RateLimitFilter;
import com.devops.copilot.modules.security.filter.ServiceTokenFilter;
import com.devops.copilot.modules.security.filter.TraceIdFilter;
import com.devops.copilot.modules.security.jwt.JwtProperties;
import com.devops.copilot.modules.security.jwt.ServiceTokenProperties;
import com.devops.copilot.modules.security.ratelimit.RateLimitProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/**
 * Spring Security 配置：无状态 JWT + 方法级 RBAC。
 *
 * <p>Filter 顺序（由先到后）：
 * TraceId → ServiceToken(/internal) → JwtAuth → RateLimit → Authorization。
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@EnableConfigurationProperties({JwtProperties.class, ServiceTokenProperties.class, RateLimitProperties.class})
public class SecurityConfig {

    @Bean
    public PasswordEncoder passwordEncoder() {
        // strength=10 是业界常用默认；过高会拖慢登录
        return new BCryptPasswordEncoder(10);
    }

    @Bean
    public SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            TraceIdFilter traceIdFilter,
            ServiceTokenFilter serviceTokenFilter,
            JwtAuthenticationFilter jwtAuthenticationFilter,
            RateLimitFilter rateLimitFilter,
            ObjectMapper objectMapper) throws Exception {

        http.csrf(AbstractHttpConfigurer::disable)
                .cors(Customizer.withDefaults())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(
                                "/api/v1/auth/register",
                                "/api/v1/auth/login",
                                "/api/v1/auth/refresh",
                                "/actuator/health",
                                "/actuator/info")
                        .permitAll()
                        // internal 由 ServiceTokenFilter 校验，此处仍要求 authenticated
                        // 但 Service Token 不会设置 Authentication —— 改为 permitAll + Filter 把关
                        .requestMatchers("/internal/**").permitAll()
                        .anyRequest().authenticated())
                .exceptionHandling(ex -> ex
                        .authenticationEntryPoint(authenticationEntryPoint(objectMapper))
                        .accessDeniedHandler(accessDeniedHandler(objectMapper)))
                .addFilterBefore(traceIdFilter, UsernamePasswordAuthenticationFilter.class)
                .addFilterAfter(serviceTokenFilter, TraceIdFilter.class)
                .addFilterAfter(jwtAuthenticationFilter, ServiceTokenFilter.class)
                .addFilterAfter(rateLimitFilter, JwtAuthenticationFilter.class);

        return http.build();
    }

    private AuthenticationEntryPoint authenticationEntryPoint(ObjectMapper objectMapper) {
        return (request, response, authException) -> {
            response.setStatus(ErrorCode.AUTH_INVALID.getStatus().value());
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            objectMapper.writeValue(
                    response.getOutputStream(),
                    ErrorResponse.of(
                            ErrorCode.AUTH_INVALID.getCode(),
                            ErrorCode.AUTH_INVALID.getDefaultMessage(),
                            TraceIds.current()));
        };
    }

    private AccessDeniedHandler accessDeniedHandler(ObjectMapper objectMapper) {
        return (request, response, accessDeniedException) -> {
            response.setStatus(ErrorCode.FORBIDDEN.getStatus().value());
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            objectMapper.writeValue(
                    response.getOutputStream(),
                    ErrorResponse.of(
                            ErrorCode.FORBIDDEN.getCode(),
                            ErrorCode.FORBIDDEN.getDefaultMessage(),
                            TraceIds.current()));
        };
    }
}
