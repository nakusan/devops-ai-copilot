-- 表：sessions（会话）
-- 外键 → users(id)、agents(id)。status：ACTIVE | ARCHIVED。
-- 索引 (user_id, updated_at DESC) 用于会话列表。

CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     BIGINT NOT NULL REFERENCES users (id),
    agent_id    BIGINT NOT NULL REFERENCES agents (id),
    title       VARCHAR(256),
    status      VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT sessions_status_chk CHECK (status IN ('ACTIVE', 'ARCHIVED'))
);

CREATE INDEX idx_sessions_user_updated ON sessions (user_id, updated_at DESC);
