package com.devops.copilot.modules.file.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.devops.copilot.modules.file.domain.entity.IngestJob;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface IngestJobMapper extends BaseMapper<IngestJob> {
}
