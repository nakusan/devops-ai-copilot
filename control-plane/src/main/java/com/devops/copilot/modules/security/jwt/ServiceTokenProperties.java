package com.devops.copilot.modules.security.jwt;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * 内网 Service Token 配置（双向 audience）。
 *
 * <ul>
 *   <li>{@code audience}：Java → Python 签发时的 aud（默认 ai-plane）</li>
 *   <li>{@code inboundAudience}：Python → Java 时本端校验要求的 aud（默认 control-plane）</li>
 * </ul>
 * 两侧共享同一 secret；用不同 aud 区分「发给谁」，避免 Token 被跨向复用。
 */
@ConfigurationProperties(prefix = "copilot.service-token")
public class ServiceTokenProperties {

    private String secret;
    private Duration ttl = Duration.ofMinutes(5);
    /** 出站：签发给 Python 时写入的 aud。 */
    private String audience = "ai-plane";
    /** 入站：校验 Python 回调本服务时要求的 aud。 */
    private String inboundAudience = "control-plane";
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

    public String getInboundAudience() {
        return inboundAudience;
    }

    public void setInboundAudience(String inboundAudience) {
        this.inboundAudience = inboundAudience;
    }

    public String getIssuer() {
        return issuer;
    }

    public void setIssuer(String issuer) {
        this.issuer = issuer;
    }
}
