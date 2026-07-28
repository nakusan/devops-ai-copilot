package com.devops.copilot.modules.security.jwt;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * 内网 Service Token 配置（Java → Python）。
 * 与用户 JWT 分离密钥，避免一套密钥既签用户又签服务。
 */
@ConfigurationProperties(prefix = "copilot.service-token")
public class ServiceTokenProperties {

    private String secret;
    private Duration ttl = Duration.ofMinutes(5);
    private String audience = "ai-plane";
    private String issuer = "control-plane";

    public String getSecret() {
        return secret;
    }

    public void setSecret(String secret) {
        this.secret = secret;
    }

    public Duration getTtl() {
        return ttl;
    }

    public void setTtl(Duration ttl) {
        this.ttl = ttl;
    }

    public String getAudience() {
        return audience;
    }

    public void setAudience(String audience) {
        this.audience = audience;
    }

    public String getIssuer() {
        return issuer;
    }

    public void setIssuer(String issuer) {
        this.issuer = issuer;
    }
}
