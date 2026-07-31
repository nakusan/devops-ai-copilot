package com.devops.copilot.modules.file.controller.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.UUID;

public class ChunkBatchRequest {

    @NotNull
    private UUID documentId;

    @NotEmpty
    @Valid
    private List<ChunkItemDto> chunks;

    public UUID getDocumentId() { return documentId; }
    public void setDocumentId(UUID documentId) { this.documentId = documentId; }
    public List<ChunkItemDto> getChunks() { return chunks; }
    public void setChunks(List<ChunkItemDto> chunks) { this.chunks = chunks; }
}
