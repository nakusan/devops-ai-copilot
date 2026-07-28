package com.devops.copilot.modules.conversation.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.devops.copilot.modules.conversation.domain.entity.Team;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface TeamMapper extends BaseMapper<Team> {
}
