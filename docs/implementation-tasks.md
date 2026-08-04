# DevOps AI Copilot — 实施任务目录

> 状态约定：`[ ]` 未做 · `[~]` 进行中 · `[x]` 完成  
> 设计资料见同目录其他文档；**本文件仅跟踪实施进度，不替代设计书**。

最后更新：2026-08-04

---

## Phase 0 — 工程骨架

- [x] P0-01～P0-12（详见历史勾选）

---

## Phase 1 — Weeks 1–3 控制面基建（1A + 2A）

### W1 JWT 鉴权 + 全局异常 + 日志规范

- [x] W1-01～W1-06

### W2 MyBatis Plus + Agent/Session CRUD

- [x] W2-01～W2-04
- [x] W2-05 Message 分页 / Chat SSE（**Phase 2 已完成**）

### W3 Redis Lua 限流 + 配额预检

- [x] W3-01～W3-02
- [x] W3-03 配额真正在 Chat 路径拦截（**Phase 2 ChatService 已挂接**）

---

## Phase 2 — Weeks 4–5 跨语言与流式（1A + 2A）

### W4 Java↔Python HTTP + Service Token

- [x] W4-01 Python：`X-Service-Token` 校验（PyJWT）
- [x] W4-02 Python：InternalChatRequest / StreamEvent 契约
- [x] W4-03 Python：Mock NDJSON stream + cancel registry
- [x] W4-04 Java：WebClient `AiPlaneClient` + NDJSON 行解析（不重试）

### W5 SSE + Message 落库

- [x] W5-01 Message 实体 / MessageService（幂等 clientMessageId）
- [x] W5-02 `GET /sessions/{id}/messages` 分页
- [x] W5-03 `POST /sessions/{id}/chat` SSE + QuotaService 挂接
- [x] W5-04 客户端断开 → cancel Python 生成

---

## Phase 3 — Weeks 6–7 AI 工作流与 RAG

- [x] W6 LangGraph + `rag_and_tool` 并行 + 流式模式 A（替换 Mock）
- [x] W7 pgvector RetrieveNode（team 过滤）

### Mock / TODO 清单（Phase 3 占位，后续补全）

| 代码位置 | 占位内容 | 原因 | 补全阶段 |
|----------|----------|------|----------|
| ~~`graph/nodes/tool.py`~~ | ~~Mock Prometheus 固定指标~~ | **已完成**：MCP Client + Mock Server（W11） | **Phase 5 / W11 ✓** |
| `graph/checkpoint/redis_saver.py` | 未启用 checkpointer | MVP 对话历史走 PG history（P7） | V2 |
| `rag/client/embedding_client.py` | hash 假向量 fallback | 无 Embedding Key 时 dev/CI 可跑 | 配置 Key 后自动切真 API |
| `graph/llm/llm_client.py` | 模式 A 图外流式 | 模式 B `astream_events` 为 V1 优化 | V1 |
| `graph/nodes/router.py` | 规则路由 | LLM intent 分类省成本 | V1.1 |

---

## Phase 4 — Weeks 8–9 异步

### W8 MinIO 上传 + Analysis Worker

- [x] W8-01 Java：MinIO `FileStorageService` + 上传策略 / 限流
- [x] W8-02 Java：`POST /api/v1/analysis/jobs` + Internal PATCH/GET
- [x] W8-03 Java：Kafka `analysis.ingest.v1` 生产
- [x] W8-04 Python：Analysis Consumer + 前 1MB 关键字解析
- [x] W8-05 Python：`analysis_lookup_node` 回调 Java 取 `result_summary`
- [x] W8-06 Schema：`analysis_jobs.error_message` / `retry_count`（写入 `09_analysis_jobs.sql`）

### W9 Kafka knowledge ingest 管道

- [x] W9-01 Java：`POST /api/v1/knowledge/documents` + ingest_jobs
- [x] W9-02 Java：Kafka `knowledge.ingest.v1` + Internal chunks/batch
- [x] W9-03 Python：下载 → 解析(pdf/md/txt) → 切块 → Embedding → Java 写库
- [x] W9-04 Python：Consumer 重试 + DLQ；**独立 Worker 进程**（`python -m app.worker`）
- [x] W9-05 Schema：`ingest_jobs.error_message`（写入 `08_ingest_jobs.sql`）

### Phase 4 明确延后

- Presigned PUT 直传（V1）
- Transactional Outbox / PENDING 补偿 Job（V1）
- MAT 级 Heap 分析（V2）
- chunks/batch HTTP 分批（维持一次全量提交）
- Kafka advertised listeners 进 Compose 改造（维持 localhost）

### Phase 4 补充决策

- [x] Service Token 双向 audience：出站 `ai-plane` / 入站 `control-plane`
- [x] Kafka Consumer 独立 Worker 进程（`python -m app.worker`）
- [x] Schema 字段直接写入 `08`/`09`（无独立补丁脚本）

---

## Phase 5 — Weeks 10–11 可观测与 MCP

- [x] W10 OTel + Grafana
  - Java：Micrometer Prometheus、`ChatMetrics`/`IngestMetrics`、Actuator 暴露、动态 spanId、`logback-spring.xml`（profile=json）
  - Python：`observability/`（otel/metrics/logging/middleware）、`GET /metrics`、关键路径埋点
  - Deploy：Compose Prometheus/Grafana；scrape `host.docker.internal`；Overview Dashboard；Postmortem / 慢请求演练文档
- [x] W11 MCP ToolNode + Mock Server
  - `mcp` SDK + stdio Mock（prometheus / postgres-readonly）
  - `McpClient` 白名单 / 超时降级；`tool_node` 接真实协议
  - HTTP：`CHAT_BACKEND=orchestrator`（默认）切到 `run_diagnosis_stream`；可回退 `mock`

---

## Phase 6 — Week 12 交付

- [ ] W12 多阶段 Dockerfile + Compose 全服务 + CI 完善

---

## Phase 2 明确不做

- LangGraph / 真 LLM / RAG / MCP
- Refresh Token Rotation
- Compose 内挂载双栈应用
