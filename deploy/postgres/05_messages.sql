-- 表：messages（消息）
-- 对话唯一真相源（原则 P7）。外键 → sessions(id)。
-- 唯一约束 (session_id, client_message_id) 用于幂等发送。

CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    role                VARCHAR(16) NOT NULL,
    content             TEXT NOT NULL,
    token_count         INT,
    metadata_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    client_message_id   VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT messages_role_chk CHECK (role IN ('user', 'assistant', 'system', 'tool'))
);

CREATE UNIQUE INDEX uq_messages_session_client_msg
    ON messages (session_id, client_message_id)
    WHERE client_message_id IS NOT NULL;

CREATE INDEX idx_messages_session_created ON messages (session_id, created_at);
