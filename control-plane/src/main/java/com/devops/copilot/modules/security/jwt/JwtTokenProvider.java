package com.devops.copilot.modules.security.jwt;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.security.domain.Role;
import com.devops.copilot.modules.security.domain.User;
import com.devops.copilot.modules.security.domain.UserPrincipal;
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
 * 用户 JWT 签发与校验。
 *
 * <p>Access / Refresh 共用密钥，用 claim {@code type} 区分，防止 refresh 被当成 access 滥用。
 */
@Component
public class JwtTokenProvider {

    public static final String CLAIM_TYPE = "type";
    public static final String CLAIM_USERNAME = "username";
    public static final String CLAIM_TEAM_ID = "teamId";
    public static final String CLAIM_ROLE = "role";
    public static final String TYPE_ACCESS = "access";
    public static final String TYPE_REFRESH = "refresh";

    private final JwtProperties properties;
    private final SecretKey key;

    public JwtTokenProvider(JwtProperties properties) {
        this.properties = properties;
        // HS256 要求密钥有足够熵；本地默认值仅用于开发
        this.key = Keys.hmacShaKeyFor(properties.getSecret().getBytes(StandardCharsets.UTF_8));
    }

    public String generateAccessToken(User user) {
        Instant now = Instant.now();
        Instant exp = now.plus(properties.getAccessTokenTtl());
        return Jwts.builder()
                .subject(String.valueOf(user.getId()))
                .claim(CLAIM_USERNAME, user.getUsername())
                .claim(CLAIM_TEAM_ID, user.getTeamId())
                .claim(CLAIM_ROLE, user.getRole())
                .claim(CLAIM_TYPE, TYPE_ACCESS)
                .issuedAt(Date.from(now))
                .expiration(Date.from(exp))
                .signWith(key)
                .compact();
    }

    public String generateRefreshToken(User user) {
        Instant now = Instant.now();
        Instant exp = now.plus(properties.getRefreshTokenTtl());
        return Jwts.builder()
                .subject(String.valueOf(user.getId()))
                .claim(CLAIM_USERNAME, user.getUsername())
                .claim(CLAIM_TEAM_ID, user.getTeamId())
                .claim(CLAIM_ROLE, user.getRole())
                .claim(CLAIM_TYPE, TYPE_REFRESH)
                .issuedAt(Date.from(now))
                .expiration(Date.from(exp))
                .signWith(key)
                .compact();
    }

    public long accessExpiresInSeconds() {
        return properties.getAccessTokenTtl().toSeconds();
    }

    /**
     * 校验 access token，并还原为 UserPrincipal。
     */
    public UserPrincipal parseAccessToken(String token) {
        Claims claims = parseClaims(token);
        requireType(claims, TYPE_ACCESS);
        return toPrincipal(claims);
    }

    /**
     * 校验 refresh token；MVP 不做 Rotation/黑名单，仅校验签名、过期与 type。
     */
    public UserPrincipal parseRefreshToken(String token) {
        Claims claims = parseClaims(token);
        requireType(claims, TYPE_REFRESH);
        return toPrincipal(claims);
    }

    private Claims parseClaims(String token) {
        try {
            return Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
        } catch (ExpiredJwtException ex) {
            throw new BizException(ErrorCode.TOKEN_EXPIRED);
        } catch (Exception ex) {
            throw new BizException(ErrorCode.AUTH_INVALID, "无效的令牌");
        }
    }

    private static void requireType(Claims claims, String expected) {
        Object type = claims.get(CLAIM_TYPE);
        if (!expected.equals(type)) {
            throw new BizException(ErrorCode.AUTH_INVALID, "令牌类型不正确");
        }
    }

    private static UserPrincipal toPrincipal(Claims claims) {
        Long userId = Long.valueOf(claims.getSubject());
        String username = claims.get(CLAIM_USERNAME, String.class);
        Long teamId = claims.get(CLAIM_TEAM_ID, Long.class);
        Role role = Role.valueOf(claims.get(CLAIM_ROLE, String.class));
        return new UserPrincipal(userId, username, teamId, role);
    }
}
