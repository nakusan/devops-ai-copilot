-- 表：agents（诊断智能体配置）
-- 全局 Agent：模型、Prompt、RAG/MCP 开关等。

CREATE TABLE agents (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    model           VARCHAR(64) NOT NULL,
    system_prompt   TEXT NOT NULL,
    enable_rag      BOOLEAN NOT NULL DEFAULT TRUE,
    enable_mcp      BOOLEAN NOT NULL DEFAULT TRUE,
    rag_top_k       INT NOT NULL DEFAULT 5,
    temperature     NUMERIC(3, 2) NOT NULL DEFAULT 0.20,
    config_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
