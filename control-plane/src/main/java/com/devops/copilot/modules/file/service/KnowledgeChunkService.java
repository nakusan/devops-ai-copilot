package com.devops.copilot.modules.file.service;

import com.devops.copilot.common.exception.BizException;
import com.devops.copilot.common.exception.ErrorCode;
import com.devops.copilot.modules.file.controller.dto.ChunkBatchRequest;
import com.devops.copilot.modules.file.controller.dto.ChunkItemDto;
import com.devops.copilot.modules.file.mapper.KnowledgeChunkMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 批量写 knowledge_chunks（含 pgvector）。重入库时先删后插，保证幂等。
 */
@Service
public class KnowledgeChunkService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeChunkService.class);

    private final KnowledgeChunkMapper chunkMapper;
    private final KnowledgeIngestService knowledgeIngestService;
    private final ObjectMapper objectMapper;

    public KnowledgeChunkService(
            KnowledgeChunkMapper chunkMapper,
            KnowledgeIngestService knowledgeIngestService,
            ObjectMapper objectMapper) {
        this.chunkMapper = chunkMapper;
        this.knowledgeIngestService = knowledgeIngestService;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public int batchInsert(ChunkBatchRequest request) {
        UUID documentId = request.getDocumentId();
        knowledgeIngestService.requireExists(documentId);

        List<ChunkItemDto> chunks = request.getChunks();
        if (chunks == null || chunks.isEmpty()) {
            throw new BizException(ErrorCode.VALIDATION_ERROR, "chunks 不能为空");
        }

        // 先删后插：同一 job 重复消费不会产生重复 chunk（UNIQUE(document_id, chunk_index)）
        chunkMapper.deleteByDocumentId(documentId);

        int inserted = 0;
        for (ChunkItemDto item : chunks) {
            if (item.getEmbedding() == null || item.getEmbedding().isEmpty()) {
                throw new BizException(ErrorCode.VALIDATION_ERROR, "embedding 不能为空");
            }
            String embeddingLiteral = toVectorLiteral(item.getEmbedding());
            String metadataJson;
            try {
                Map<String, Object> meta = item.getMetadata() == null ? Map.of() : item.getMetadata();
                metadataJson = objectMapper.writeValueAsString(meta);
            } catch (JsonProcessingException ex) {
                throw new BizException(ErrorCode.VALIDATION_ERROR, "metadata 序列化失败");
            }
            UUID chunkId = item.getId() == null ? UUID.randomUUID() : item.getId();
            chunkMapper.insertOne(
                    chunkId.toString(),
                    documentId.toString(),
                    item.getChunkIndex(),
                    item.getContent(),
                    embeddingLiteral,
                    metadataJson);
            inserted++;
        }
        log.info("chunks batch inserted documentId={} count={}", documentId, inserted);
        return inserted;
    }

    /**
     * pgvector 文本字面量：{@code [0.1,0.2,...]}。
     */
    static String toVectorLiteral(List<Double> embedding) {
        return embedding.stream()
                .map(d -> String.format(java.util.Locale.ROOT, "%.8f", d))
                .collect(Collectors.joining(",", "[", "]"));
    }
}
