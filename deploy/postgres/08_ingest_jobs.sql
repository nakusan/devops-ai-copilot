-- 表：ingest_jobs（知识异步入库任务）
-- 外键 → knowledge_documents(id)。

CREATE TABLE ingest_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES knowledge_documents (id) ON DELETE CASCADE,
    kafka_offset    BIGINT,
    status          VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    retry_count     INT NOT NULL DEFAULT 0,
    -- Worker 回调失败原因（截断后写入，供前端 / 排障展示）
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ingest_jobs_status_chk
        CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'))
);

CREATE INDEX idx_ingest_jobs_status_created ON ingest_jobs (status, created_at);
