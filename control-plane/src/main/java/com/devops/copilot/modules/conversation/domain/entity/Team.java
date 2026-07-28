package com.devops.copilot.modules.conversation.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

import java.time.OffsetDateTime;

/** 研发组：配额上限来源。 */
@TableName("teams")
public class Team {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String name;

    @TableField("daily_token_limit")
    private Long dailyTokenLimit;

    @TableField("created_at")
    private OffsetDateTime createdAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public Long getDailyTokenLimit() { return dailyTokenLimit; }
    public void setDailyTokenLimit(Long dailyTokenLimit) { this.dailyTokenLimit = dailyTokenLimit; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime createdAt) { this.createdAt = createdAt; }
}
