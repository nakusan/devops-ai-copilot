package com.devops.copilot.modules.conversation.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.conversation.client.dto.InternalChatRequest;
import com.devops.copilot.modules.conversation.controller.dto.AgentResponse;
import com.devops.copilot.modules.conversation.controller.dto.CreateAgentRequest;
import com.devops.copilot.modules.conversation.controller.dto.UpdateAgentRequest;
import com.devops.copilot.modules.conversation.domain.entity.Agent;
import com.devops.copilot.modules.conversation.mapper.AgentMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.List;

@Service
public class AgentService {

    private final AgentMapper agentMapper;

    public AgentService(AgentMapper agentMapper) {
        this.agentMapper = agentMapper;
    }

    public List<AgentResponse> list() {
        return agentMapper.selectList(new LambdaQueryWrapper<Agent>().orderByAsc(Agent::getId))
                .stream()
                .map(this::toResponse)
                .toList();
    }

    public AgentResponse get(Long id) {
        return toResponse(requireExists(id));
    }

    /** 创建 Session 前校验 Agent 存在。 */
    public void ensureExists(Long agentId) {
        requireExists(agentId);
    }

    /**
     * 组装发给 Python 的 AgentConfig。
     * config_json 中的扩展字段（如 maxHistoryMessages）覆盖列默认值。
     */
    public InternalChatRequest.AgentConfigDto getAgentForChat(Long agentId) {
        Agent agent = requireExists(agentId);
        InternalChatRequest.AgentConfigDto dto = new InternalChatRequest.AgentConfigDto();
        dto.setModel(agent.getModel());
        dto.setSystemPrompt(agent.getSystemPrompt());
        dto.setEnableRag(Boolean.TRUE.equals(agent.getEnableRag()));
        dto.setEnableMcp(Boolean.TRUE.equals(agent.getEnableMcp()));
        dto.setRagTopK(agent.getRagTopK() != null ? agent.getRagTopK() : 5);
        dto.setTemperature(agent.getTemperature() != null ? agent.getTemperature().doubleValue() : 0.2);
        if (agent.getConfigJson() != null) {
            Object maxHist = agent.getConfigJson().get("maxHistoryMessages");
            if (maxHist instanceof Number n) {
                dto.setMaxHistoryMessages(n.intValue());
            }
            Object threshold = agent.getConfigJson().get("ragScoreThreshold");
            if (threshold instanceof Number n) {
                dto.setRagScoreThreshold(n.doubleValue());
            }
            Object mcp = agent.getConfigJson().get("mcpServers");
            if (mcp instanceof List<?> list) {
                dto.setMcpServers(list.stream().map(String::valueOf).toList());
            }
        }
        return dto;
    }

    @Transactional
    public AgentResponse create(CreateAgentRequest req) {
        OffsetDateTime now = OffsetDateTime.now();
        Agent agent = new Agent();
        agent.setName(req.getName());
        agent.setModel(req.getModel());
        agent.setSystemPrompt(req.getSystemPrompt());
        agent.setEnableRag(req.getEnableRag() != null ? req.getEnableRag() : Boolean.TRUE);
        agent.setEnableMcp(req.getEnableMcp() != null ? req.getEnableMcp() : Boolean.TRUE);
        agent.setRagTopK(req.getRagTopK() != null ? req.getRagTopK() : 5);
        agent.setTemperature(req.getTemperature());
        agent.setConfigJson(req.getConfigJson() != null ? req.getConfigJson() : new HashMap<>());
        agent.setCreatedAt(now);
        agent.setUpdatedAt(now);
        agentMapper.insert(agent);
        return toResponse(agent);
    }

    @Transactional
    public AgentResponse update(Long id, UpdateAgentRequest req) {
        Agent agent = requireExists(id);
        if (req.getName() != null) {
            agent.setName(req.getName());
        }
        if (req.getModel() != null) {
            agent.setModel(req.getModel());
        }
        if (req.getSystemPrompt() != null) {
            agent.setSystemPrompt(req.getSystemPrompt());
        }
        if (req.getEnableRag() != null) {
            agent.setEnableRag(req.getEnableRag());
        }
        if (req.getEnableMcp() != null) {
            agent.setEnableMcp(req.getEnableMcp());
        }
        if (req.getRagTopK() != null) {
            agent.setRagTopK(req.getRagTopK());
        }
        if (req.getTemperature() != null) {
            agent.setTemperature(req.getTemperature());
        }
        if (req.getConfigJson() != null) {
            agent.setConfigJson(req.getConfigJson());
        }
        agent.setUpdatedAt(OffsetDateTime.now());
        agentMapper.updateById(agent);
        return toResponse(agent);
    }

    @Transactional
    public void delete(Long id) {
        requireExists(id);
        // 表无软删字段：MVP 硬删。若已被 Session 引用，DB 外键会拦截。
        agentMapper.deleteById(id);
    }

    private Agent requireExists(Long id) {
        Agent agent = agentMapper.selectById(id);
        if (agent == null) {
            throw new BizException(ErrorCode.NOT_FOUND, "Agent 不存在");
        }
        return agent;
    }

    private AgentResponse toResponse(Agent a) {
        return new AgentResponse(
                a.getId(),
                a.getName(),
                a.getModel(),
                a.getSystemPrompt(),
                a.getEnableRag(),
                a.getEnableMcp(),
                a.getRagTopK(),
                a.getTemperature(),
                a.getConfigJson(),
                a.getCreatedAt(),
                a.getUpdatedAt());
    }
}
