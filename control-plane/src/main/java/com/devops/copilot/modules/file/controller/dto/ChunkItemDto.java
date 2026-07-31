package com.devops.copilot.modules.file.controller.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public class ChunkItemDto {

    private UUID id;

    @NotNull
    private Integer chunkIndex;

    @NotBlank
    private String content;

    @NotEmpty
    private List<Double> embedding;

    private Map<String, Object> metadata;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public Integer getChunkIndex() { return chunkIndex; }
    public void setChunkIndex(Integer chunkIndex) { this.chunkIndex = chunkIndex; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public List<Double> getEmbedding() { return embedding; }
    public void setEmbedding(List<Double> embedding) { this.embedding = embedding; }
    public Map<String, Object> getMetadata() { return metadata; }
    public void setMetadata(Map<String, Object> metadata) { this.metadata = metadata; }
}
