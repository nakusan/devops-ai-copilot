package com.devops.copilot.modules.conversation.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.devops.copilot.modules.conversation.domain.entity.SessionEntity;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface SessionMapper extends BaseMapper<SessionEntity> {
}
