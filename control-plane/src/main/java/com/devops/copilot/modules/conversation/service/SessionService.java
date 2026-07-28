package com.devops.copilot.modules.conversation.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.conversation.controller.dto.CreateSessionRequest;
import com.devops.copilot.modules.conversation.controller.dto.SessionResponse;
import com.devops.copilot.modules.conversation.controller.dto.UpdateSessionRequest;
import com.devops.copilot.modules.conversation.domain.entity.SessionEntity;
import com.devops.copilot.modules.conversation.domain.enums.SessionStatus;
import com.devops.copilot.modules.conversation.mapper.SessionMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 会话生命周期。所有按 id 的操作必须做归属校验，防止 UUID 枚举越权。
 */
@Service
public class SessionService {

    private final SessionMapper sessionMapper;
    private final AgentService agentService;

    public SessionService(SessionMapper sessionMapper, AgentService agentService) {
        this.sessionMapper = sessionMapper;
        this.agentService = agentService;
    }

    @Transactional
    public SessionResponse create(Long userId, CreateSessionRequest req) {
        agentService.ensureExists(req.getAgentId());
        OffsetDateTime now = OffsetDateTime.now();
        SessionEntity session = new SessionEntity();
        session.setId(UUID.randomUUID());
        session.setUserId(userId);
        session.setAgentId(req.getAgentId());
        session.setTitle(req.getTitle() == null || req.getTitle().isBlank() ? "新会话" : req.getTitle());
        session.setStatus(SessionStatus.ACTIVE.name());
        session.setCreatedAt(now);
        session.setUpdatedAt(now);
        sessionMapper.insert(session);
        return toResponse(session);
    }

    public List<SessionResponse> listMine(Long userId) {
        return sessionMapper.selectList(new LambdaQueryWrapper<SessionEntity>()
                        .eq(SessionEntity::getUserId, userId)
                        .orderByDesc(SessionEntity::getUpdatedAt))
                .stream()
                .map(this::toResponse)
                .toList();
    }

    public SessionResponse getMine(UUID sessionId, Long userId) {
        return toResponse(requireOwnedSession(sessionId, userId, false));
    }

    @Transactional
    public SessionResponse update(UUID sessionId, Long userId, UpdateSessionRequest req) {
        // 更新允许操作已归档会话（例如改标题），故 allowArchived=true
        SessionEntity session = requireOwnedSession(sessionId, userId, true);
        if (req.getTitle() != null) {
            session.setTitle(req.getTitle());
        }
        if (req.getStatus() != null) {
            validateStatus(req.getStatus());
            session.setStatus(req.getStatus());
        }
        session.setUpdatedAt(OffsetDateTime.now());
        sessionMapper.updateById(session);
        return toResponse(session);
    }

    @Transactional
    public void archive(UUID sessionId, Long userId) {
        SessionEntity session = requireOwnedSession(sessionId, userId, true);
        session.setStatus(SessionStatus.ARCHIVED.name());
        session.setUpdatedAt(OffsetDateTime.now());
        sessionMapper.updateById(session);
    }

    /**
     * 归属 + 存在性校验。
     *
     * @param allowArchived false 时拒绝已归档会话（后续 Chat 会用）
     */
    public SessionEntity requireOwnedSession(UUID sessionId, Long userId, boolean allowArchived) {
        SessionEntity session = sessionMapper.selectById(sessionId);
        if (session == null) {
            throw new BizException(ErrorCode.NOT_FOUND, "会话不存在");
        }
        // 关键：不能只靠 UUID 难猜；必须比对 owner
        if (!session.getUserId().equals(userId)) {
            throw new BizException(ErrorCode.FORBIDDEN, "无权访问该会话");
        }
        if (!allowArchived && SessionStatus.ARCHIVED.name().equals(session.getStatus())) {
            throw new BizException(ErrorCode.FORBIDDEN, "会话已归档");
        }
        return session;
    }

    /** 聊天活动时刷新会话排序时间。 */
    @Transactional
    public void touchUpdatedAt(UUID sessionId) {
        SessionEntity session = sessionMapper.selectById(sessionId);
        if (session == null) {
            return;
        }
        session.setUpdatedAt(OffsetDateTime.now());
        sessionMapper.updateById(session);
    }

    private static void validateStatus(String status) {
        try {
            SessionStatus.valueOf(status);
        } catch (IllegalArgumentException ex) {
            throw new BizException(ErrorCode.VALIDATION_ERROR, "非法的会话状态: " + status);
        }
    }

    private SessionResponse toResponse(SessionEntity s) {
        return new SessionResponse(
                s.getId(),
                s.getUserId(),
                s.getAgentId(),
                s.getTitle(),
                s.getStatus(),
                s.getCreatedAt(),
                s.getUpdatedAt());
    }
}
