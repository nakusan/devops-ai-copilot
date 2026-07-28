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
 * 内网 Service Token：证明调用方是 control-plane，而不是终端用户。
 *
 * <p>W4 起 Java WebClient 会携带此 Token 调 Python；本阶段先实现签发/校验与 Filter。
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

    public void verify(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .requireAudience(properties.getAudience())
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
