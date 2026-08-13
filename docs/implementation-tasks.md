# DevOps AI Copilot — 实施任务目录

> 状态约定：`[ ]` 未做 · `[~]` 进行中 · `[x]` 完成  
> 设计资料见同目录其他文档；**本文件仅跟踪实施进度，不替代设计书**。

最后更新：2026-08-13（Phase 7 P1~P4 代码落地）

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
- ~~Kafka advertised listeners 进 Compose 改造（维持 localhost）~~ → **W12 已补全双监听**

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

- [x] W12 多阶段 Dockerfile + Compose 全服务 + CI 完善
  - `control-plane/Dockerfile`、`ai-plane/Dockerfile`（多阶段；非 root；healthcheck）
  - Compose：`profile=apps` 拉起 control-plane / ai-plane / ai-plane-worker；Kafka 双监听
  - CI：Java `test`+`package`；Python ruff + **pyright** + pytest；Docker buildx + compose config
  - 工程化补强：`copilot_ro` 只读角色；Prometheus 容器服务发现抓取
  - Makefile：`stack-up` / `stack-down`；`ci-local` 对齐本地检查

---

## Phase 7 — 链路追踪补全（设计见 `6.10链路追踪落地设计(Tracing).md`）

> 背景：当前只有 traceId 字符串在日志里串联，Python span 因未配 OTLP 出口被全部丢弃，Java 侧无真实 span。
> 决策：Java 走 `micrometer-tracing-bridge-otel`；后端只加 Tempo 直连；Kafka 用 parent-child；前端不纳入。

### P7-1 Python span 出口（半天，收益最大）

- [x] P7-01 Tempo 服务 + Grafana Tempo datasource + Compose `OTEL_EXPORTER_OTLP_ENDPOINT`
- [x] P7-02 `otel.py` 补 Resource / 显式 sampler / `shutdown_otel()`；`worker.py` / FastAPI lifespan 退出前 flush
- [x] P7-03 `logging.py` traceId 优先级翻转（OTel span 优先于 `extra`）
- [x] P7-04 实测异步生成器跨 `yield` 持有 span（§9 R1）：同任务内父子关系正常；结论已回填 `6.10`；联调时再观察 detach 警告
  - 联调剩余：`make stack-up` 后在 Grafana Tempo 验证 chat span 树（见设计书 §5.5 / §10 P1-6、P1-7）
  - [x] P1 补丁 F4：`FastAPIInstrumentor.exclude_spans=["send","receive"]`，消除流式 `http send` 噪音

### P7-2 Java 接入同一棵树

- [x] P7-05 `micrometer-tracing-bridge-otel` + `opentelemetry-exporter-otlp`；`management.tracing` / `management.otlp`；`spring.reactor.context-propagation=auto`；Kafka `observation-enabled` 预开
- [x] P7-06 `TraceIdFilter` 重构：从 `Tracer.currentSpan()` 取 traceId；`@Order(+2)`；单测重写
- [x] P7-07 `AiPlaneClient` 删手拼 traceparent 与 `padTraceId`；`TraceIds` 删假 `newSpanId`；Compose `TRACING_OTLP_ENDPOINT` / `TRACING_SAMPLE_RATE`
  - 联调剩余：Tempo 中验证跨 `control-plane` + `ai-plane` 父子 span（§6.6 / §10 P2-1~P2-3）

### P7-3 异步链路与关键埋点

- [x] P7-08 `spring.kafka.template.observation-enabled` + Python consumer 从 record header `extract`
- [x] P7-09 asyncpg 自动埋点；补 `rag.embed` / `graph.router` / `analysis.process` span
- [x] P7-10 清理重复 server span（FastAPIInstrumentor 与自研 middleware 二选一）；metrics `path` label 改路由模板
- [x] P7-11 `llm.completion` 补 `gen_ai.*` 语义属性（模型 / 温度 / token 用量）
  - 联调剩余：上传 PDF 同树；asyncpg SELECT 可见（§7.6 / §10 P3-1、P3-2）

### P7-4 三信号互跳

- [x] P7-12 Tempo↔Prometheus 跳转、exemplars、Overview Dashboard 慢请求 TraceQL 面板
- [x] P7-13 更新 `runbooks/slow-request-drill.md` 为「先看 trace」路径
  - 联调剩余：Dashboard exemplar 跳转 + 一次 Postmortem 演练（§10 P4-1、P4-2、P4-4）

### Phase 7 明确延后

- Loki + Alloy 日志集中化（V2）
- OTel Collector + 尾采样（V2）
- 前端 RUM / OTel Web SDK（V2）
- Java JDBC / Redis 自动埋点（V2，需 Agent）
- LLM 自动埋点包（V2，待 GenAI 语义约定稳定）

---

## Phase 2 明确不做

- LangGraph / 真 LLM / RAG / MCP
- Refresh Token Rotation
- Compose 内挂载双栈应用
