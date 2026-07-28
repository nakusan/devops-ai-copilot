-- 表：knowledge_documents（知识库文档元数据）
-- MVP：同 team_id 成员可共享检索。
-- status：PENDING | PROCESSING | COMPLETED | FAILED。

CREATE TABLE knowledge_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL REFERENCES users (id),
    team_id         BIGINT NOT NULL REFERENCES teams (id),
    title           VARCHAR(256) NOT NULL,
    object_key      VARCHAR(512) NOT NULL,
    mime_type       VARCHAR(64),
    size_bytes      BIGINT,
    status          VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    error_message   TEXT,
    metadata_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT knowledge_documents_status_chk
        CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'))
);

CREATE INDEX idx_knowledge_documents_team_status ON knowledge_documents (team_id, status);
