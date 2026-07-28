package com.devops.copilot.modules.conversation.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.devops.copilot.modules.conversation.client.dto.InternalChatRequest;
import com.devops.copilot.modules.conversation.controller.dto.ChatRequest;
import com.devops.copilot.modules.conversation.controller.dto.MessageResponse;
import com.devops.copilot.modules.conversation.controller.dto.PageResponse;
import com.devops.copilot.modules.conversation.domain.entity.Message;
import com.devops.copilot.modules.conversation.domain.enums.MessageRole;
import com.devops.copilot.modules.conversation.mapper.MessageMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class MessageService {

    private final MessageMapper messageMapper;

    public MessageService(MessageMapper messageMapper) {
        this.messageMapper = messageMapper;
    }

    /**
     * 保存用户消息。若带 clientMessageId 且已存在，返回已有记录（幂等，避免重复扣配额/重复流）。
     *
     * @return result.created=false 表示命中幂等
     */
    @Transactional
    public SaveUserResult saveUserMessage(UUID sessionId, ChatRequest req) {
        if (req.getClientMessageId() != null && !req.getClientMessageId().isBlank()) {
            Message existing = messageMapper.selectOne(new LambdaQueryWrapper<Message>()
                    .eq(Message::getSessionId, sessionId)
                    .eq(Message::getClientMessageId, req.getClientMessageId())
                    .eq(Message::getRole, MessageRole.user.name())
                    .last("LIMIT 1"));
            if (existing != null) {
                return new SaveUserResult(existing, false);
            }
        }

        Message msg = new Message();
        msg.setId(UUID.randomUUID());
        msg.setSessionId(sessionId);
        msg.setRole(MessageRole.user.name());
        msg.setContent(req.getContent());
        msg.setClientMessageId(blankToNull(req.getClientMessageId()));
        msg.setMetadataJson(new HashMap<>());
        msg.setCreatedAt(OffsetDateTime.now());
        messageMapper.insert(msg);
        return new SaveUserResult(msg, true);
    }

    /**
     * 加载历史：最近 limit 条，按时间正序返回，且排除本轮 user 消息。
     *
     * <p>实现：先按 created_at DESC 取 limit+过滤，再 reverse。排除用 id，避免 content 相同误伤。
     */
    public List<InternalChatRequest.ChatMessageDto> loadHistory(
            UUID sessionId, int limit, UUID excludeMessageId) {
        List<Message> recent = messageMapper.selectList(new LambdaQueryWrapper<Message>()
                .eq(Message::getSessionId, sessionId)
                .ne(excludeMessageId != null, Message::getId, excludeMessageId)
                .in(Message::getRole, MessageRole.user.name(), MessageRole.assistant.name(), MessageRole.system.name())
                .orderByDesc(Message::getCreatedAt)
                .last("LIMIT " + Math.max(1, limit)));

        List<InternalChatRequest.ChatMessageDto> history = new ArrayList<>();
        for (int i = recent.size() - 1; i >= 0; i--) {
            Message m = recent.get(i);
            history.add(new InternalChatRequest.ChatMessageDto(m.getRole(), m.getContent()));
        }
        return history;
    }

    @Transactional
    public Message saveAssistantMessage(UUID sessionId, String content, Map<String, Object> metadata) {
        Message msg = new Message();
        msg.setId(UUID.randomUUID());
        msg.setSessionId(sessionId);
        msg.setRole(MessageRole.assistant.name());
        msg.setContent(content == null ? "" : content);
        msg.setMetadataJson(metadata != null ? metadata : new HashMap<>());
        Object usage = metadata != null ? metadata.get("usage") : null;
        if (usage instanceof Map<?, ?> usageMap) {
            Object total = usageMap.get("totalTokens");
            if (total instanceof Number n) {
                msg.setTokenCount(n.intValue());
            }
        }
        msg.setCreatedAt(OffsetDateTime.now());
        messageMapper.insert(msg);
        return msg;
    }

    public PageResponse<MessageResponse> listBySession(UUID sessionId, long page, long size) {
        long p = Math.max(1, page);
        long s = Math.min(100, Math.max(1, size));
        Page<Message> mp = messageMapper.selectPage(
                new Page<>(p, s),
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getSessionId, sessionId)
                        .orderByAsc(Message::getCreatedAt));
        List<MessageResponse> items = mp.getRecords().stream().map(this::toResponse).toList();
        return new PageResponse<>(items, mp.getTotal(), p, s);
    }

    private MessageResponse toResponse(Message m) {
        return new MessageResponse(
                m.getId(),
                m.getSessionId(),
                m.getRole(),
                m.getContent(),
                m.getTokenCount(),
                m.getMetadataJson(),
                m.getClientMessageId(),
                m.getCreatedAt());
    }

    private static String blankToNull(String v) {
        return v == null || v.isBlank() ? null : v;
    }

    public record SaveUserResult(Message message, boolean created) {
    }
}
