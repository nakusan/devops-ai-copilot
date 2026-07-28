# DevOps AI Copilot — 实施任务目录

> 状态约定：`[ ]` 未做 · `[~]` 进行中 · `[x]` 完成  
> 设计资料见同目录其他文档；**本文件仅跟踪实施进度，不替代设计书**。

最后更新：2026-07-28

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
| `graph/nodes/tool.py` | Mock Prometheus 固定指标 | MCP Client/Server 未实现 | Phase 5 / W11 |
| `graph/nodes/analysis.py` | 返回 `analysis_summary=None` | Analysis Worker + Java API 未就绪 | Phase 4 / W8 |
| `graph/checkpoint/redis_saver.py` | 未启用 checkpointer | MVP 对话历史走 PG history（P7） | V2 |
| `rag/client/embedding_client.py` | hash 假向量 fallback | 无 Embedding Key 时 dev/CI 可跑 | 配置 Key 后自动切真 API |
| `graph/llm/llm_client.py` | 模式 A 图外流式 | 模式 B `astream_events` 为 V1 优化 | V1 |
| `graph/nodes/router.py` | 规则路由 | LLM intent 分类省成本 | V1.1 |
| `consumers/knowledge_ingest.py` | 空 stub | Kafka ingest 管道 | Phase 4 / W9 |
| `consumers/analysis_ingest.py` | 空 stub | Analysis ingest | Phase 4 / W8 |

---

## Phase 4 — Weeks 8–9 异步

- [ ] W8 MinIO 上传 + Analysis Worker 简化解析
- [ ] W9 Kafka ingest 管道

---

## Phase 5 — Weeks 10–11 可观测与 MCP

- [ ] W10 OTel + Grafana
- [ ] W11 MCP ToolNode + Mock Server

---

## Phase 6 — Week 12 交付

- [ ] W12 多阶段 Dockerfile + Compose 全服务 + CI 完善

---

## Phase 2 明确不做

- LangGraph / 真 LLM / RAG / MCP
- Refresh Token Rotation
- Compose 内挂载双栈应用
