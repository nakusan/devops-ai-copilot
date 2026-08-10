package com.devops.copilot.modules.conversation.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.devops.copilot.common.mybatis.JsonbTypeHandler;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;

/**
 * Agent 配置实体，对应 03_agents.sql。
 * config_json 用 JsonbTypeHandler 映射 PostgreSQL JSONB。
 */
@TableName(value = "agents", autoResultMap = true)
public class Agent {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String name;
    private String model;

    @TableField("system_prompt")
    private String systemPrompt;

    @TableField("enable_rag")
    private Boolean enableRag;

    @TableField("enable_mcp")
    private Boolean enableMcp;

    @TableField("rag_top_k")
    private Integer ragTopK;

    private BigDecimal temperature;

    @TableField(value = "config_json", typeHandler = JsonbTypeHandler.class)
    private Map<String, Object> configJson;

    @TableField("created_at")
    private OffsetDateTime createdAt;

    @TableField("updated_at")
    private OffsetDateTime updatedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public String getSystemPrompt() { return systemPrompt; }
    public void setSystemPrompt(String systemPrompt) { this.systemPrompt = systemPrompt; }
    public Boolean getEnableRag() { return enableRag; }
    public void setEnableRag(Boolean enableRag) { this.enableRag = enableRag; }
    public Boolean getEnableMcp() { return enableMcp; }
    public void setEnableMcp(Boolean enableMcp) { this.enableMcp = enableMcp; }
    public Integer getRagTopK() { return ragTopK; }
    public void setRagTopK(Integer ragTopK) { this.ragTopK = ragTopK; }
    public BigDecimal getTemperature() { return temperature; }
    public void setTemperature(BigDecimal temperature) { this.temperature = temperature; }
    public Map<String, Object> getConfigJson() { return configJson; }
    public void setConfigJson(Map<String, Object> configJson) { this.configJson = configJson; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime createdAt) { this.createdAt = createdAt; }
    public OffsetDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(OffsetDateTime updatedAt) { this.updatedAt = updatedAt; }
}
