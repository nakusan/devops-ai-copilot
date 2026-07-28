package com.devops.copilot.modules.security.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.security.domain.Role;
import com.devops.copilot.modules.security.domain.TokenPair;
import com.devops.copilot.modules.security.domain.User;
import com.devops.copilot.modules.security.domain.UserPrincipal;
import com.devops.copilot.modules.security.jwt.JwtTokenProvider;
import com.devops.copilot.modules.security.mapper.UserMapper;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;

/**
 * 注册 / 登录 / 刷新。
 *
 * <p>失败统一抛 AUTH_INVALID，避免通过「用户不存在 / 密码错误」差异枚举账号。
 */
@Service
public class AuthService {

    /** MVP：新用户默认加入 teams.id=1（见 init SQL 种子）。 */
    public static final long DEFAULT_TEAM_ID = 1L;

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    public AuthService(
            UserMapper userMapper, PasswordEncoder passwordEncoder, JwtTokenProvider jwtTokenProvider) {
        this.userMapper = userMapper;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Transactional
    public TokenPair register(String username, String rawPassword) {
        Long count = userMapper.selectCount(new LambdaQueryWrapper<User>().eq(User::getUsername, username));
        if (count != null && count > 0) {
            // 注册场景可以提示冲突；登录场景才必须统一文案
            throw new BizException(ErrorCode.CONFLICT, "用户名已存在");
        }

        User user = new User();
        user.setUsername(username);
        user.setPasswordHash(passwordEncoder.encode(rawPassword));
        user.setTeamId(DEFAULT_TEAM_ID);
        user.setRole(Role.USER.name());
        user.setCreatedAt(OffsetDateTime.now());
        userMapper.insert(user);
        return issueTokens(user);
    }

    public TokenPair login(String username, String rawPassword) {
        User user = userMapper.selectOne(new LambdaQueryWrapper<User>().eq(User::getUsername, username));
        /*
         * 防用户枚举：即使用户不存在，也走一次 matches。
         * 使用固定占位 hash，避免每次 encode 带来明显耗时差异。
         */
        String placeholderHash = "$2a$10$dXJ3SW6G7P50lGmMkkmwe.20cQQubK3.HZWzG3YB1tlRy.fqvM/BG";
        String hash = user != null ? user.getPasswordHash() : placeholderHash;
        boolean matches = passwordEncoder.matches(rawPassword, hash);
        if (user == null || !matches) {
            throw new BizException(ErrorCode.AUTH_INVALID);
        }
        return issueTokens(user);
    }

    /**
     * Refresh：用 refresh token 换新的 access+refresh。
     * MVP 不做 Rotation 黑名单；生产应吊销旧 refresh。
     */
    public TokenPair refresh(String refreshToken) {
        UserPrincipal principal = jwtTokenProvider.parseRefreshToken(refreshToken);
        User user = userMapper.selectById(principal.getUserId());
        if (user == null) {
            throw new BizException(ErrorCode.AUTH_INVALID);
        }
        return issueTokens(user);
    }

    private TokenPair issueTokens(User user) {
        return new TokenPair(
                jwtTokenProvider.generateAccessToken(user),
                jwtTokenProvider.generateRefreshToken(user),
                jwtTokenProvider.accessExpiresInSeconds());
    }
}
