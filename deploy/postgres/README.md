# PostgreSQL 库表（手工初始化）

对齐详细设计 §5.2。文件按编号排序，保证
`docker-entrypoint-initdb.d` 以外键安全顺序执行。

| 文件 | 说明 |
|------|------|
| `00_extensions.sql` | `vector`、`pgcrypto` 扩展 |
| `01_teams.sql` | teams + 默认种子数据 |
| `02_users.sql` | users |
| `03_agents.sql` | agents |
| `04_sessions.sql` | sessions |
| `05_messages.sql` | messages |
| `06_knowledge_documents.sql` | knowledge_documents |
| `07_knowledge_chunks.sql` | knowledge_chunks + HNSW 索引 |
| `08_ingest_jobs.sql` | ingest_jobs |
| `09_analysis_jobs.sql` | analysis_jobs |
| `10_seed_agent.sql` | 默认诊断 Agent |
| `11_seed_admin_user.sql` | 本地 admin / Admin123! |
| `12_seed_knowledge_rag.sql` | RAG 验收种子（STATUS_899 + 固定向量） |

Compose 将本目录挂载到 `/docker-entrypoint-initdb.d`。
脚本**仅在数据卷首次为空时**执行。
