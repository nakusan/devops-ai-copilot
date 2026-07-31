package com.devops.copilot.modules.security.jwt;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;

/**
 * 内网 Service Token：双向签发/校验。
 *
 * <ul>
 *   <li>{@link #issue()}：Java → Python，aud={@code audience}（ai-plane）</li>
 *   <li>{@link #verify(String)}：Python → Java，要求 aud={@code inboundAudience}（control-plane）</li>
 * </ul>
 */
@Component
public class ServiceTokenProvider {

    public static final String HEADER = "X-Service-Token";
    public static final String CLAIM_TYPE = "type";
    public static final String TYPE_SERVICE = "service";

    private final ServiceTokenProperties properties;
    private final SecretKey key;

    public ServiceTokenProvider(ServiceTokenProperties properties) {
        this.properties = properties;
        this.key = Keys.hmacShaKeyFor(properties.getSecret().getBytes(StandardCharsets.UTF_8));
    }

    /** 签发给 Python（出站）。 */
    public String issue() {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(properties.getIssuer())
                .audience().add(properties.getAudience()).and()
                .claim(CLAIM_TYPE, TYPE_SERVICE)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(properties.getTtl())))
                .signWith(key)
                .compact();
    }

    /**
     * 校验入站 Token（Python 回调 /internal）。
     * 必须带 inboundAudience，不能用出站 audience，否则 Java 自签 Token 也能打本服务 internal API。
     */
    public void verify(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .requireAudience(properties.getInboundAudience())
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            if (!TYPE_SERVICE.equals(claims.get(CLAIM_TYPE))) {
                throw new BizException(ErrorCode.AUTH_INVALID, "Service Token 类型不正确");
            }
        } catch (BizException ex) {
            throw ex;
        } catch (ExpiredJwtException ex) {
            throw new BizException(ErrorCode.TOKEN_EXPIRED, "Service Token 已过期");
        } catch (Exception ex) {
            throw new BizException(ErrorCode.AUTH_INVALID, "无效的 Service Token");
        }
    }
}
