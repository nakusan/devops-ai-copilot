-- 表：knowledge_chunks（知识切块 + 向量）
-- Embedding 维度 = 1536（MVP 详细设计 §5.4）。外键 → knowledge_documents(id)。
-- HNSW 余弦距离索引，用于相似度检索。

CREATE TABLE knowledge_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES knowledge_documents (id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    metadata_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_knowledge_chunks_doc_index UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_knowledge_chunks_embedding
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
