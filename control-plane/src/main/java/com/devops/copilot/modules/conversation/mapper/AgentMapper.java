package com.devops.copilot.modules.conversation.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.devops.copilot.modules.conversation.domain.entity.Agent;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AgentMapper extends BaseMapper<Agent> {
}
