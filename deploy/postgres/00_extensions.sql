-- 扩展：必须最先执行。
-- vector：pgvector 向量检索；pgcrypto：提供 gen_random_uuid()。

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
