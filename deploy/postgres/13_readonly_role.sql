-- 只读角色（工程化：最小权限 / least privilege）
-- AI Plane RAG 检索只用此账号；禁止写库，降低 SQL 注入与误写风险。
-- 密码仅用于本地 Compose；生产应改密密钥管理注入。

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'copilot_ro') THEN
        CREATE ROLE copilot_ro LOGIN PASSWORD 'copilot_ro';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE copilot TO copilot_ro;
GRANT USAGE ON SCHEMA public TO copilot_ro;

-- RAG 只读所需表（见 pgvector_store 的 JOIN 查询）
GRANT SELECT ON TABLE knowledge_documents TO copilot_ro;
GRANT SELECT ON TABLE knowledge_chunks TO copilot_ro;
