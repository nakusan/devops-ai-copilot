package com.devops.copilot.modules.conversation.controller.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;
import java.util.Map;

public class CreateAgentRequest {

    @NotBlank
    @Size(max = 128)
    private String name;

    @NotBlank
    @Size(max = 64)
    private String model;

    @NotBlank
    private String systemPrompt;

    private Boolean enableRag = true;
    private Boolean enableMcp = true;
    private Integer ragTopK = 5;

    @DecimalMin("0.0")
    @DecimalMax("2.0")
    private BigDecimal temperature = new BigDecimal("0.20");

    private Map<String, Object> configJson;

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
}
