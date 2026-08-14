-- 已有库：embedding 从 1536 → 1024（BAAI/bge-m3 等）。
-- 旧向量维度不兼容，清空后需重新入库；种子用 seed-hash 版本不会与 bge-m3 混检。
-- 幂等：若已是 1024 则跳过 ALTER。

DO $$
DECLARE
    dim INT;
BEGIN
    SELECT atttypmod INTO dim
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public'
      AND c.relname = 'knowledge_chunks'
      AND a.attname = 'embedding'
      AND NOT a.attisdropped;

    -- pgvector：atttypmod = 维度
    IF dim IS DISTINCT FROM 1024 THEN
        DROP INDEX IF EXISTS idx_knowledge_chunks_embedding;
        TRUNCATE TABLE knowledge_chunks;
        ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(1024);
        CREATE INDEX idx_knowledge_chunks_embedding
            ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
    END IF;
END $$;

-- 默认 Agent 切到智谱免费 Flash（聊天实际用 agents.model，不是仅靠 LLM_MODEL env）
UPDATE agents
SET model = 'glm-4.7-flash',
    updated_at = NOW()
WHERE id = 1
  AND model IS DISTINCT FROM 'glm-4.7-flash';
