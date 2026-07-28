package com.devops.copilot.modules.security.config;

import com.devops.copilot.modules.security.filter.JwtAuthenticationFilter;
import com.devops.copilot.modules.security.filter.RateLimitFilter;
import com.devops.copilot.modules.security.filter.ServiceTokenFilter;
import com.devops.copilot.modules.security.filter.TraceIdFilter;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 禁用 Security Filter 的 Servlet 容器自动注册。
 *
 * <p>原因：{@code OncePerRequestFilter} 标了 {@code @Component} 会被 Boot 自动挂到 Servlet Filter 链，
 * 同时又在 {@link SecurityConfig} 里 {@code addFilter*}，导致同一请求执行两遍（MDC 被提前 clear 等诡异问题）。
 * 这里显式 {@code setEnabled(false)}，只保留 Security 链中的那一次。
 */
@Configuration
public class FilterRegistrationConfig {

    @Bean
    public FilterRegistrationBean<TraceIdFilter> disableTraceIdFilter(TraceIdFilter filter) {
        return disabled(filter);
    }

    @Bean
    public FilterRegistrationBean<ServiceTokenFilter> disableServiceTokenFilter(ServiceTokenFilter filter) {
        return disabled(filter);
    }

    @Bean
    public FilterRegistrationBean<JwtAuthenticationFilter> disableJwtFilter(JwtAuthenticationFilter filter) {
        return disabled(filter);
    }

    @Bean
    public FilterRegistrationBean<RateLimitFilter> disableRateLimitFilter(RateLimitFilter filter) {
        return disabled(filter);
    }

    private static <T extends jakarta.servlet.Filter> FilterRegistrationBean<T> disabled(T filter) {
        FilterRegistrationBean<T> bean = new FilterRegistrationBean<>(filter);
        bean.setEnabled(false);
        return bean;
    }
}
