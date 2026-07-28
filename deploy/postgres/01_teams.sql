-- 表：teams（研发组）
-- MVP 种子：id=1，name='default'，日 Token 配额 100000。
-- 新用户注册默认归属 team_id = 1。

CREATE TABLE teams (
    id                  BIGSERIAL PRIMARY KEY,
    name                VARCHAR(64) NOT NULL UNIQUE,
    daily_token_limit   BIGINT NOT NULL DEFAULT 100000,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO teams (id, name, daily_token_limit)
VALUES (1, 'default', 100000);

-- 显式插入 id 后，同步序列，避免后续插入冲突
SELECT setval(pg_get_serial_sequence('teams', 'id'), (SELECT MAX(id) FROM teams));
