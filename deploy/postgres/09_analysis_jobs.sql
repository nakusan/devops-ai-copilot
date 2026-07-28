-- 表：analysis_jobs（大文件分析任务）
-- 外键 → users(id)。file_type：HEAP_DUMP | GC_LOG | APP_LOG。

CREATE TABLE analysis_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             BIGINT NOT NULL REFERENCES users (id),
    object_key          VARCHAR(512) NOT NULL,
    file_type           VARCHAR(32) NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    result_summary      TEXT,
    result_object_key   VARCHAR(512),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT analysis_jobs_file_type_chk
        CHECK (file_type IN ('HEAP_DUMP', 'GC_LOG', 'APP_LOG')),
    CONSTRAINT analysis_jobs_status_chk
        CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'))
);

CREATE INDEX idx_analysis_jobs_user_created ON analysis_jobs (user_id, created_at DESC);
