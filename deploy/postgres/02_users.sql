-- 表：users（用户）
-- 外键 → teams(id)。role：USER | ADMIN。password_hash：BCrypt。

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(64) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    team_id         BIGINT NOT NULL REFERENCES teams (id),
    role            VARCHAR(16) NOT NULL DEFAULT 'USER',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT users_role_chk CHECK (role IN ('USER', 'ADMIN'))
);

CREATE INDEX idx_users_team_id ON users (team_id);
