package com.devops.copilot.modules.file.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.devops.copilot.common.mybatis.JsonbTypeHandler;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

/**
 * 知识库文档元数据，对应 06_knowledge_documents.sql。
 * object_key 不暴露给前端；status 是用户可见的流水线镜像。
 */
@TableName(value = "knowledge_documents", autoResultMap = true)
public class KnowledgeDocument {

    @TableId(type = IdType.INPUT)
    private UUID id;

    @TableField("user_id")
    private Long userId;

    @TableField("team_id")
    private Long teamId;

    private String title;

    @TableField("object_key")
    private String objectKey;

    @TableField("mime_type")
    private String mimeType;

    @TableField("size_bytes")
    private Long sizeBytes;

    private String status;

    @TableField("error_message")
    private String errorMessage;

    @TableField(value = "metadata_json", typeHandler = JsonbTypeHandler.class)
    private Map<String, Object> metadataJson;

    @TableField("created_at")
    private OffsetDateTime createdAt;

    @TableField("updated_at")
    private OffsetDateTime updatedAt;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }
    public Long getTeamId() { return teamId; }
    public void setTeamId(Long teamId) { this.teamId = teamId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getObjectKey() { return objectKey; }
    public void setObjectKey(String objectKey) { this.objectKey = objectKey; }
    public String getMimeType() { return mimeType; }
    public void setMimeType(String mimeType) { this.mimeType = mimeType; }
    public Long getSizeBytes() { return sizeBytes; }
    public void setSizeBytes(Long sizeBytes) { this.sizeBytes = sizeBytes; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public Map<String, Object> getMetadataJson() { return metadataJson; }
    public void setMetadataJson(Map<String, Object> metadataJson) { this.metadataJson = metadataJson; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime createdAt) { this.createdAt = createdAt; }
    public OffsetDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(OffsetDateTime updatedAt) { this.updatedAt = updatedAt; }
}
