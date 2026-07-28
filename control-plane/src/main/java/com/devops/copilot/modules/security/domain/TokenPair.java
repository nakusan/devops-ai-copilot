package com.devops.copilot.modules.security.domain;

/**
 * 登录 / 刷新成功后返回给客户端的令牌对。
 */
public record TokenPair(
        String accessToken,
        String refreshToken,
        long expiresInSeconds
) {
}
