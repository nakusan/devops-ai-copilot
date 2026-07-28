package com.devops.copilot.modules.security.domain;

/**
 * MVP 粗粒度角色。Spring Security 会自动加 ROLE_ 前缀时需注意：
 * 本项目 {@link UserPrincipal#getAuthorities()} 直接返回 ROLE_USER / ROLE_ADMIN。
 */
public enum Role {
    USER,
    ADMIN
}
