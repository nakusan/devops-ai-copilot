package com.devops.copilot.modules.file.mapper;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.UUID;

/**
 * knowledge_chunks 批量写入。
 *
 * <p>embedding 以文本形式传入（如 {@code [0.1,0.2,...]}），再 {@code CAST AS vector}。
 * 原因：MyBatis 无原生 pgvector 类型；经 Java API 写库符合架构 P2。
 */
@Mapper
public interface KnowledgeChunkMapper {

    @Delete("DELETE FROM knowledge_chunks WHERE document_id = #{documentId}")
    int deleteByDocumentId(@Param("documentId") UUID documentId);

    @Insert("""
            INSERT INTO knowledge_chunks (id, document_id, chunk_index, content, embedding, metadata_json)
            VALUES (
              #{id}::uuid,
              #{documentId}::uuid,
              #{chunkIndex},
              #{content},
              CAST(#{embeddingLiteral} AS vector),
              CAST(#{metadataJson} AS jsonb)
            )
            """)
    int insertOne(
            @Param("id") String id,
            @Param("documentId") String documentId,
            @Param("chunkIndex") int chunkIndex,
            @Param("content") String content,
            @Param("embeddingLiteral") String embeddingLiteral,
            @Param("metadataJson") String metadataJson);
}
