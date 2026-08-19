# 智能研发运维辅助系统 (DevOps AI Copilot) — 详细设计方案 V1.0

> 本文档基于你提供的《架构设计总纲》展开，目标是：**读完即可理解系统脉络、模块边界、数据怎么流、每个技术解决什么问题、关键实现逻辑怎么写。**
>
> 文档结构：**背景与边界 → 总体架构 → 技术栈 → 数据模型 → 模块详细设计 → 核心链路 → API 契约 → 安全与可观测 → 部署拓扑 → 演进约束**。

---

## 目录

1. [系统定位与边界](#1-系统定位与边界)
2. [总体架构](#2-总体架构)
3. [技术栈与选型理由](#3-技术栈与选型理由)
4. [核心概念与术语表](#4-核心概念与术语表)
5. [数据模型设计](#5-数据模型设计)
6. [功能模块详细设计](#6-功能模块详细设计)
7. [核心数据链路与时序](#7-核心数据链路与时序)
8. [API 设计](#8-api-设计)
9. [跨服务契约与错误模型](#9-跨服务契约与错误模型)
10. [安全设计](#10-安全设计)
11. [可观测性设计](#11-可观测性设计)
12. [非功能需求与容量假设](#12-非功能需求与容量假设)
13. [部署与本地开发拓扑](#13-部署与本地开发拓扑)
14. [与 12 周路线的映射](#14-与-12-周路线的映射)
15. [MVP 范围与刻意不做](#15-mvp-范围与刻意不做)

---

## 1. 系统定位与边界

### 1.1 一句话定义

**DevOps AI Copilot** 是企业内部面向研发/运维人员的 **AI 辅助排查平台后端**：把 **私有知识（Wiki/复盘文档）、历史日志文件、实时监控数据** 通过 **RAG + Agent + MCP Tool** 串联起来，以 **流式对话** 方式输出诊断结论，同时保证 **鉴权、限流、审计、可观测、异步大文件处理**。

### 1.2 解决的核心痛点

| 痛点 | 现状 | 本系统如何解决 |
|------|------|----------------|
| **数据孤岛** | 查 STATUS_899 要翻 Wiki、Kibana、Grafana、DB | RAG 召回内部字典 + MCP 拉实时指标 + Agent 汇总 |
| **通用 LLM 幻觉** | 无企业上下文 | 强制 RAG grounding + Tool 只读查询 |
| **大文件阻塞** | 50MB heap dump 拖垮 Web 线程 | MinIO 直存 + Kafka 异步解析 + 202 响应 |
| **排查门槛高** | 新人不懂链路 | 会话历史 + 结构化 Agent 诊断图 |
| **无法上线 Demo** | 无权限/限额/日志 | Java 控制面统一治理 |

### 1.3 系统边界（谁做什么）

```text
┌─────────────────────────────────────────────────────────────┐
│                        本系统范围内                           │
├─────────────────────────────────────────────────────────────┤
│ Java 控制面：鉴权、限流、会话/元数据、文件入口、SSE、发 Kafka   │
│ Python 智能面：LangGraph、RAG、Embedding、MCP Client、LLM   │
│ 中间件：PostgreSQL+pgvector、Redis、Kafka、MinIO             │
│ 可观测：OTel、Prometheus、Grafana                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     本系统范围外（对接）                        │
├─────────────────────────────────────────────────────────────┤
│ LLM 提供商（DeepSeek/Qwen/OpenAI 兼容 API）                  │
│ 企业 Prometheus / 只读 DB（经 MCP Server 或 Mock）            │
│ 前端（未来 Next.js；MVP 用 API 工具）                         │
│ 真实 Kibana/完整 APM（V2 对接，MVP 用上传日志文件替代）         │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 架构原则（实现时必须遵守）

| # | 原则 | 含义 |
|---|------|------|
| P1 | **Java 是唯一公网入口** | 客户端只调 Java；Python 仅内网 |
| P2 | **Python 不持有 PG 写权限** | 向量写入经 Java API；状态变更经 Java API；**检索可用 `readonly` 账号直连 PG** |
| P3 | **SSE 终点在 Java** | 利于鉴权、审计、统一断连与取消 |
| P4 | **主路径同步、副作用异步** | 聊天流式同步；入库/解析走 Kafka |
| P5 | **Tool 默认只读** | MCP/SQL/Prometheus 禁止写操作 |
| P6 | **全链路 TraceId** | Java 生成，透传 Python → LLM → Kafka Consumer |
| P7 | **对话历史以 PG 为准** | `messages` 表为唯一对话真相源；每轮 Java 传 `history`；Redis checkpoint MVP 不启用 |
| P8 | **内外流式协议分离** | 对内 Java↔Python 用 NDJSON；对客户端用 SSE；Java 负责格式转换 |
| P9 | **Trace 以 W3C traceparent 为准** | `X-Trace-Id` 由 traceparent 派生，供日志与报障 |

---

## 2. 总体架构

### 2.1 逻辑分层架构

```text
                         ┌──────────────┐
                         │   Client     │
                         │ (Web/API)    │
                         └──────┬───────┘
                                │ HTTPS
                    ┌───────────▼───────────┐
                    │   Java Control Plane   │
                    │   (Spring Boot 3)      │
                    ├───────────────────────┤
                    │ Gateway & Security     │
                    │ Session & Metadata     │
                    │ File Ingress           │
                    │ SSE Termination        │
                    │ Kafka Producer         │
                    └─────┬─────────┬───────┘
                          │         │
           ┌──────────────┼─────────┼──────────────┐
           ▼              ▼         ▼              ▼
      PostgreSQL       Redis      MinIO         Kafka
      (+ pgvector)                              │
                          │                     │ consume
                          │         ┌───────────▼───────────┐
                          │         │  Python AI Plane        │
                          │         │  (FastAPI)            │
                          │         ├───────────────────────┤
                          └────────►│ LangGraph Orchestrator│
                                    │ RAG / Embedding       │
                                    │ MCP Client            │
                                    │ LLM Router            │
                                    └───────────┬───────────┘
                                                │
                                    ┌───────────▼───────────┐
                                    │ External LLM APIs     │
                                    │ MCP Servers (Mock/Real)│
                                    └───────────────────────┘

        ─ ─ ─ ─ ─ ─ ─ ─ Cross-cutting ─ ─ ─ ─ ─ ─ ─ ─ ─
              OpenTelemetry  |  Prometheus  |  Structured Logs
```

### 2.2 控制面 vs 智能面职责矩阵

| 能力 | Java | Python | 说明 |
|------|:----:|:------:|------|
| JWT 签发/校验 | ✅ | ❌ | Python 用 Service Token |
| 用户/会话 CRUD | ✅ | ❌ | |
| API 限流/配额 | ✅ | 辅助 | Java 入口拦截；Python 可二次校验 token 预算 |
| SSE 对客户端 | ✅ | ❌ | |
| 文件上传接收 | ✅ | ❌ | 流式写 MinIO |
| Kafka 生产 | ✅ | ❌ | |
| Kafka 消费 | ❌ | ✅ | 解析/向量化 |
| LangGraph 状态机 | ❌ | ✅ | |
| RAG 检索/Embedding | ❌ | ✅ | 读 pgvector |
| MCP Client | ❌ | ✅ | |
| LLM 流式调用 | ❌ | ✅ | |
| 业务表状态更新 | ✅ | 回调 API | ingest job 状态 |

### 2.3 诊断编排（ReAct / LLM function calling）

```text
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         ▼
              ┌─────────────────────┐
              │ Orchestrator ReAct  │
              │ complete_with_tools │
              └──────────┬──────────┘
           tool_calls    │    无 tool_calls
        ┌────────────────┼────────────────┐
        ▼                                 ▼
┌───────────────┐                 ┌───────────────┐
│ ToolExecutor  │                 │ 最终流式回答  │
│ retrieve/MCP/ │──回灌 messages──│ stream/切片   │
│ analysis      │                 └───────┬───────┘
└───────┬───────┘                         ▼
        │                            ┌─────────┐
        └──────── 再规划 ───────────►│   END   │
                                     └─────────┘
```

**工具由模型选择**（不再 Router 正则 / 关键词 resolver）。`done.intent` 由实际调用过的工具推导（`direct` / `rag` / `tool` / `rag_and_tool` / `analysis`）。详见 `docs/6.5`。

**对话上下文（P7）**：

- **唯一真相源**：PostgreSQL `messages` 表；每轮 Java 查最近 N 条作为 `history` 传入 Python。
- **轮次产出**：assistant 的 `metadata_json` 存 citations、toolCalls、usage、intent（审计快照）。
- **Checkpoint**：当前不启用；V2 仅用于多步 Tool 中断恢复，且 **不存 messages**。

---

## 3. 技术栈与选型理由

### 3.1 总览表

| 层级 | 技术 | 版本建议 | 解决什么问题 | 为何选它（2026 语境） |
|------|------|----------|--------------|----------------------|
| 控制面语言 | Java | 21 LTS | 企业级稳定运行时 | 国内后端岗基本盘；Actuator 生态成熟 |
| 控制面框架 | Spring Boot | 3.3+ | Web/Security/配置一体化 | 事实标准；与 MyBatis/OTel 集成成熟 |
| ORM | MyBatis Plus | 3.5+ | 可控 SQL + CRUD 效率 | 贴近企业；向量表仍可手写 SQL |
| 数据库 | PostgreSQL | 16+ | 事务 + JSONB + 扩展 | AI 产品常用；**pgvector 同库** 减少组件 |
| 向量 | pgvector | 0.7+ | 语义检索 | MVP 足够；免独立向量库运维 |
| 缓存/限流 | Redis | 7+ | 限流、配额计数、热点 | 行业标准 |
| 消息 | Kafka | 3.x | 异步解耦、重试、DLQ | 事件驱动训练目标；比 RabbitMQ 更贴近大厂 |
| 对象存储 | MinIO | latest | 大文件、预签名直传 | S3 兼容；本地/云一致 |
| 智能面 | Python + FastAPI | 3.12 / 0.11+ | AI 生态 | LangGraph/LlamaIndex 首选语言 |
| Agent 框架 | LangGraph | 0.2+ | 有状态 DAG | 比裸 LangChain 更可控 |
| LLM 接入 | openai SDK / LiteLLM | - | 多模型兼容 | DeepSeek/Qwen 均 OpenAI 兼容 |
| Embedding | 同厂商 Embedding API | - | 向量化 | 与 LLM 统一账单与网关 |
| MCP | mcp Python SDK | - | 标准化 Tool | 2025-2026 工具协议趋势 |
| 流式（对外） | SSE | - | 逐 token 推送给客户端 | AI 产品标准交互 |
| 流式（对内） | NDJSON (`application/x-ndjson`) | - | Java↔Python 每行一个 JSON 事件 | 比 SSE 更易解析、透传 |
| Java→Python | WebClient (Reactor) | - | 非阻塞按行读 NDJSON | 在 Java 侧转换为 SSE |
| 追踪 | OpenTelemetry | 1.x | 跨 Java/Python/DB | 双栈必备 |
| 指标 | Micrometer + Prometheus | - | QPS/延迟/JVM | Spring 原生 |
| 可视化 | Grafana | - | 大盘 | 与 Prometheus 配套 |
| 容器 | Docker Compose | - | 一键环境 | 12 周不引入 K8s |
| CI | GitHub Actions | - | 构建/检查 | 作品集标配 |

### 3.2 刻意不引入的技术

| 技术 | 原因 |
|------|------|
| Kubernetes | 学习 ROI 低；Compose 够 |
| 独立向量库（Milvus/Qdrant） | MVP pgvector 足够 |
| Spring Cloud / Dubbo | 双 HTTP 服务即可 |
| NestJS | Python 侧生态更强 |
| 前端框架（MVP） | 后端工程训练优先 |

---

## 4. 核心概念与术语表

| 术语 | 定义 |
|------|------|
| **Session（会话）** | 一次排查话题的容器，含多轮 Message |
| **Message** | 单条 user/assistant/system/tool 消息 |
| **Agent** | 诊断智能体配置：模型、prompt、工具开关、RAG 范围 |
| **Knowledge Document** | 上传的 PDF/Markdown/复盘文档元数据 |
| **Knowledge Chunk** | 文档切块 + embedding 向量 |
| **Ingest Job** | 异步入库任务（PENDING→PROCESSING→COMPLETED/FAILED） |
| **Analysis Job** | 大日志/heap 文件异步分析任务 |
| **Trace ID** | 全链路请求标识，W3C `traceparent` |
| **Quota** | 用户/研发组的 Token 或请求次数配额 |
| **MCP Server** | 对外部系统（Prometheus/DB）的标准化 Tool 宿主 |

---

## 5. 数据模型设计

### 5.1 ER 关系概览

```text
Team ──< User ──< Session ──< Message
  │
  └──< KnowledgeDocument ──< KnowledgeChunk (vector)
  │
  └──< IngestJob / AnalysisJob

Agent (全局配置；V1.1 可按 team 过滤可见性)
```

### 5.2 核心表结构（PostgreSQL）

#### `teams`（MVP 最小表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| name | VARCHAR(64) UNIQUE | 如 `default` |
| daily_token_limit | BIGINT | 日 Token 配额上限，默认 100000 |
| created_at | TIMESTAMPTZ | |

MVP 种子数据：`INSERT INTO teams (id, name, daily_token_limit) VALUES (1, 'default', 100000);`  
新用户注册默认 `team_id = 1`。

#### `users`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| username | VARCHAR(64) UNIQUE | |
| password_hash | VARCHAR(255) | BCrypt |
| team_id | BIGINT FK → teams.id | 研发组，用于限额 |
| role | VARCHAR(16) | `USER` / `ADMIN` |
| created_at | TIMESTAMPTZ | |

#### `agents`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | |
| name | VARCHAR(128) | 如「线上故障诊断助手」 |
| model | VARCHAR(64) | `deepseek-chat` |
| system_prompt | TEXT | 诊断人设与约束 |
| enable_rag | BOOLEAN | |
| enable_mcp | BOOLEAN | |
| rag_top_k | INT | 默认 5 |
| temperature | NUMERIC(3,2) | |
| config_json | JSONB | 扩展参数 |

#### `sessions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | Java 生成 |
| user_id | BIGINT FK | |
| agent_id | BIGINT FK | |
| title | VARCHAR(256) | 首条消息摘要 |
| status | VARCHAR(16) | `ACTIVE` / `ARCHIVED` |
| created_at / updated_at | TIMESTAMPTZ | |

索引：`(user_id, updated_at DESC)`

#### `messages`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| session_id | UUID FK | |
| role | VARCHAR(16) | user/assistant/system/tool |
| content | TEXT | 最终完整内容 |
| token_count | INT | 可选 |
| metadata_json | JSONB | tool_calls、引用 chunk ids |
| client_message_id | VARCHAR(64) | 幂等 |
| created_at | TIMESTAMPTZ | |

唯一索引：`(session_id, client_message_id)` 防重复发送

#### `knowledge_documents`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | BIGINT FK | 上传者 |
| team_id | BIGINT FK → teams.id | **MVP：同 team 成员可检索** |
| title | VARCHAR(256) | |
| object_key | VARCHAR(512) | MinIO key |
| mime_type | VARCHAR(64) | |
| size_bytes | BIGINT | |
| status | VARCHAR(16) | PENDING/PROCESSING/COMPLETED/FAILED |
| error_message | TEXT | |
| metadata_json | JSONB | 含 `embedding_model_version` |
| created_at / updated_at | TIMESTAMPTZ | |

#### `knowledge_chunks`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| document_id | UUID FK | |
| chunk_index | INT | |
| content | TEXT | |
| embedding | vector(1536) | 维度与 `embedding_config` 一致，见 §5.4 |
| metadata_json | JSONB | 页码、章节、来源 |

索引：`CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);`

#### `ingest_jobs`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| document_id | UUID FK | |
| kafka_offset | BIGINT | 可选，对账 |
| status | VARCHAR(16) | |
| retry_count | INT | |
| created_at / updated_at | TIMESTAMPTZ | |

#### `analysis_jobs`（大文件分析）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | BIGINT FK | |
| object_key | VARCHAR(512) | MinIO |
| file_type | VARCHAR(32) | `HEAP_DUMP` / `GC_LOG` / `APP_LOG` |
| status | VARCHAR(16) | |
| result_summary | TEXT | 解析结论摘要 |
| result_object_key | VARCHAR(512) | 结构化结果 JSON 存 MinIO |
| created_at / updated_at | TIMESTAMPTZ | |

### 5.3 Redis Key 设计

| Key | 类型 | TTL | 用途 |
|-----|------|-----|------|
| `ratelimit:ip:{ip}` | string/zset | 1min | IP 防抖 |
| `ratelimit:user:{userId}` | hash | 1min | 令牌桶 |
| `quota:team:{teamId}:daily_tokens` | string | 24h | 日 Token 配额 |
| `lg:checkpoint:{sessionId}` | string | 7d | LangGraph 图中间态（**V2 可选**，MVP 不启用） |
| `idempotent:msg:{clientMessageId}` | string | 1h | 幂等 |

### 5.4 Embedding 模型配置（MVP 固定）

| 配置项 | MVP 值 | 说明 |
|--------|--------|------|
| `EMBEDDING_MODEL` | `text-embedding-v3`（阿里 DashScope）或 `text-embedding-3-small`（OpenAI 兼容） | **全环境统一一家**，禁止混用 |
| `EMBEDDING_DIM` | `1536`（随模型文档确认，入库前校验） | 与 `knowledge_chunks.embedding vector(N)` 一致 |
| `EMBEDDING_MODEL_VERSION` | 配置项，如 `v1` | 写入 `knowledge_documents.metadata_json` |

**换模型策略**：

1. 修改 `EMBEDDING_MODEL` + 确认新维度 → 若维度变化需 migration 改 `vector(N)`  
2. 标记旧文档 `embedding_model_version` 过期  
3. 触发全量 re-ingest（Admin 接口或批量重发 Kafka）  
4. 检索时 **仅查与当前 `EMBEDDING_MODEL_VERSION` 一致的 chunks**

MVP 不建独立 `embedding_config` 表，用环境变量 + 文档 metadata 即可。

---

## 6. 功能模块详细设计

### 6.1 网关与安全模块（Java）

#### 功能清单

- 注册/登录/刷新 Token
- JWT 校验过滤器
- 统一 `GlobalExceptionHandler` → RFC 风格错误体
- CORS（仅开发环境开放）
- Service Token 签发（Java→Python）

#### 实现逻辑

```text
请求进入
  → JwtAuthFilter 解析 Authorization: Bearer
  → 无效/过期 → 401 AUTH_INVALID
  → 有效 → SecurityContext 写入 UserPrincipal(userId, teamId, role)
  → RateLimitFilter（Redis Lua）
  → Controller
```

**Token 结构（JWT Claims）**：

```json
{
  "sub": "userId",
  "teamId": 1,
  "role": "USER",
  "type": "access",
  "exp": ...
}
```

Access 15min + Refresh 7d（Refresh 存 PG 或 Redis 黑名单轮换）。

#### 限流 Lua 逻辑（令牌桶简化版）

```text
INPUT: userId, cost=1, capacity=60, refill_rate=1/sec
1. 读取 tokens, last_refill_ts
2. 按时间补充 tokens
3. tokens >= cost ? 扣减并允许 : 返回 429 RATE_LIMITED
```

研发组配额：聊天前估算 `estimated_tokens`，查 `quota:team:{teamId}:daily_tokens`；不足返回 **429** `QUOTA_EXCEEDED`。

---

### 6.2 会话与元数据模块（Java）

#### 功能清单

- Session CRUD（创建、列表、归档）
- Message 历史分页查询
- Agent 配置 CRUD（Admin）
- 聊天入口 `POST /api/v1/sessions/{id}/chat`（SSE）

#### 聊天入口实现逻辑（核心）

```text
1. 鉴权 + 限流 + 配额预检
2. 校验 session 属于当前 user
3. 幂等检查 clientMessageId → 若已存在 **返回已有 assistant 结果（不调 Python）**
4. INSERT message(role=user, content=...)
5. 构建 InternalChatRequest:
     sessionId, agentId, userMessage, history (最近 N 条，**不含本条 user**), traceId, agentConfig
6. WebClient POST python/internal/v1/chat/stream (Accept: application/x-ndjson)
7. 订阅 Python NDJSON 流（每行一个 JSON）:
     - 每收到 {"type":"token",...} → 转为 SSE event: "token"
     - 收到 {"type":"done",...} → 聚合 fullText → INSERT message(role=assistant, metadata_json)
     - 更新 quota 实际消耗
8. 客户端断开 → subscription.dispose() + 调 Python cancel API
```

**历史加载策略（P7）**：

- DB 查最近 20 条 message 作为 `history`，**不包含本轮刚 INSERT 的 user 消息**（当前轮走 `userMessage` 字段，避免 prompt 重复）
- `history` 为 **唯一对话上下文来源**
- 本轮 citations、toolCalls 等写入 assistant `metadata_json`；MVP 不使用 Redis checkpoint

**SSE 与 JWT（MVP）**：仅在 **建立 SSE 连接时** 校验 Access Token 一次；连接存续期间不因 15min 过期而中断。前端应在过期前静默 refresh，新开会话须带新 Token。

---

### 6.3 文件与调度模块（Java）

#### 两种上传模式

| 模式 | 适用 | 流程 |
|------|------|------|
| **服务端流式上传** | ≤20MB MVP | `multipart` → Java 流式写 MinIO |
| **预签名直传** | 大文件 50MB+ | Java 返回 presigned PUT URL → 客户端直传 MinIO → 回调 confirm |

#### 知识文档入库逻辑

```text
POST /api/v1/knowledge/documents
  → 写 MinIO (object_key)
  → INSERT knowledge_documents status=PENDING
  → INSERT ingest_jobs status=PENDING
  → Kafka publish KnowledgeIngestEvent → topic `knowledge.ingest.v1`
  → HTTP 202 { jobId, documentId, status: "PENDING" }
```

#### 大文件分析逻辑

```text
POST /api/v1/analysis/jobs
  → 同上，topic 为 `analysis.ingest.v1`
  → Python 消费者离线解析（heap/GC 特征提取）
  → 完成后 result_summary 写入 analysis_jobs
  → 可选：WebSocket/SSE 通知或轮询 GET /analysis/jobs/{id}
```

#### Kafka 生产者可靠性

- `acks=all`
- 消息 key = `documentId`（保序）
- 发送失败：DB 标 `FAILED`，人工可重试
- DLQ topic：`knowledge.ingest.dlq.v1`，消费失败超 3 次转入

**Kafka 投递失败补偿（MVP）**：定时 Job（每 5min）扫描 `ingest_jobs` 中 `status=PENDING` 且 `created_at < now()-5min` 的记录，重新 publish；超过 3 次标 `FAILED`。

---

### 6.4 知识检索模块 RAG（Python）

#### 管道阶段

```text
原始文件 (MinIO)
  → 下载到临时目录
  → 文档解析 (pdf: pypdf / md: raw / log: text)
  → 清洗（去页眉页脚、空白）
  → Semantic Chunking（按段落 + max_tokens=512 overlap=64）
  → 批量 Embedding API（batch=32）
  → 写入 knowledge_chunks（经 Java internal API 或受限 DB 连接）
  → 更新 document status=COMPLETED
```

#### 检索逻辑（RetrieveNode）

```text
INPUT: userQuery, topK, filters(optional document_ids)
1. query_embedding = embed(userQuery)
2. SQL:
   SELECT id, content, document_id, 1 - (embedding <=> :query) AS score
   FROM knowledge_chunks c
   JOIN knowledge_documents d ON d.id = c.document_id
   WHERE d.status = 'COMPLETED'
     AND d.team_id = :teamId          -- MVP：同 team 共享知识库
     AND c.embedding_model_version = :currentVersion
   ORDER BY embedding <=> :query
   LIMIT :topK
3. score < threshold(0.7) 的丢弃，避免幻觉
4. OUTPUT: List[ChunkRef] 带入 SynthesizeNode
```

#### Prompt 组装（SynthesizeNode）

```text
system: {agent.system_prompt}
context:
  【内部知识】
  [1] {chunk1.content} (来源: {doc.title})
  ...
  【实时数据】（若有 Tool 结果）
  {tool_result}
user: {user_message}

约束：仅基于 context 回答；不足则说明「知识库无记录」；引用标注 [n]
```

---

### 6.5 智能体编排模块（Python / LangGraph）

#### State 结构（TypedDict）

```python
class DiagnosisState(TypedDict):
    session_id: str
    trace_id: str
    user_message: str
    intent: str                    # rag | tool | rag_and_tool | analysis | direct
    retrieved_chunks: list
    tool_results: list
    messages: list                 # LangChain messages
    final_answer: str
    token_usage: dict
```

#### RouterNode 逻辑

```text
用轻量规则 + 可选 LLM 分类（按优先级匹配）：
  - 含「分析结果」「heap」「上传的文件」→ intent=analysis
  - 同时命中 RAG 词（STATUS_/错误码/为什么）AND Tool 词（当前/连接数/CPU）→ intent=rag_and_tool（并行）
  - 仅含 Tool 词 → intent=tool
  - 仅含 RAG 词 → intent=rag
  - enable_rag=false → intent=direct
  - 默认 → rag
```

`rag_and_tool` 走 FanOutNode：`asyncio.gather(retrieve, tool)` 并行执行后合并进 state，再进 SynthesizeNode。

MVP 可 **规则优先**，降低不稳定。V1 增加 `rag_then_tool`（含「根据/按照手册/排查步骤」等依赖信号时串行）。

#### ToolNode（MCP）

```text
根据 intent 调用 MCP Server:
  - prometheus_query(query="db_connections")
  - readonly_sql(sql="SELECT count(*) FROM pg_stat_activity")
返回结构化 JSON → 写入 state.tool_results
```

**安全**：MCP Server 独立进程；仅白名单 tool；SQL 仅 SELECT；PromQL 仅只读。

#### 流式输出（MVP 模式 A，正式选型）

```text
1. graph.ainvoke 跑完 router + retrieve/tool/fan_out/analysis（同步，快）
2. API 层 build_messages(state) 后单独调 LLM stream=True
3. 每 chunk yield NDJSON { type: "token", text }
4. 结束 yield { type: "done", usage, citations }
```

V1 可统一为整图 `astream_events`（模式 B）。

---

### 6.8 大文件分析模块 Analysis Worker（Python）

> 详见独立文档 `6.8大文件分析模块Analysis Worker(Python).md`

**定位**：消费 `analysis.ingest.v1`，对 heap/GC/app 日志做 **MVP 简化解析**，结果写入 `analysis_jobs`，供 LangGraph `analysis` 意图查询。

**MVP 解析器**（不引入 Eclipse MAT）：

```text
下载 MinIO 文件 → 读取前 1MB 文本 → 关键字统计（OOM, Full GC, Exception）
→ 生成 result_summary（纯文本摘要）
→ 可选 result_object_key 存 JSON 详情
→ PATCH Java internal API status=COMPLETED
```

**与聊天集成**：用户问「上传的 heap 分析结果」→ Router `intent=analysis` → `GET /internal/v1/analysis-jobs` 读 `result_summary`。

---

### 6.6 工具挂载模块 MCP（Python）

#### 架构

```text
FastAPI (AI Plane)
    └── MCP Client
            ├── prometheus-mcp-server (HTTP/SSE)
            └── postgres-readonly-mcp-server (Mock or real)
```

#### MVP Mock 方案

- 本地起一个 **Mock MCP Server**，固定返回 `db_connections: 42`
- Week 11 验证链路；生产替换真实 endpoint

#### 调用时序

```text
ToolNode
  → mcp_client.list_tools()
  → mcp_client.call_tool("prometheus_query", { "query": "..." })
  → 超时 5s，失败写入 state.tool_results=[{error: "..."}]
  → SynthesizeNode 基于错误如实告知用户
```

---

### 6.7 遥测监控模块

| 信号类型 | 实现 | 采集点 |
|----------|------|--------|
| **Metrics** | Micrometer → Prometheus | Java QPS、latency、chat_total、ingest_lag |
| **Traces** | OTel SDK | Java filter 创建 root span；WebClient 注入 traceparent |
| **Logs** | JSON + traceId | Logback JSON；Python structlog |

**自定义指标示例**：

- `chat_requests_total{status}`
- `chat_stream_duration_seconds`
- `rag_retrieval_latency_seconds`
- `kafka_consume_lag{topic}`
- `llm_tokens_total{model}`

---

## 7. 核心数据链路与时序

### 7.1 场景一：RAG 流式诊断（同步链路）

```text
Client          Java                 Redis        PostgreSQL      Python           pgvector      LLM
  │ POST /chat     │                     │              │              │               │            │
  ├───────────────►│ JWT+限流+配额        │              │              │               │            │
  │                ├────────────────────►│              │              │               │            │
  │                │ INSERT user_msg     │              │              │               │            │
  │                ├────────────────────────────────────►│              │               │            │
  │                │ POST /internal/chat/stream ──────────────────────►│               │            │
  │                │                     │              │              ├─ RouterNode   │            │
  │                │                     │              │              ├─ RetrieveNode────────────►│
  │                │                     │              │              │◄─ topK chunks │            │
  │                │                     │              │              ├─ SynthesizeNode────────────►│ stream
  │                │◄── chunk stream ───────────────────────────────────│◄──────────────────────────│
  │◄── SSE token ──│                     │              │              │               │            │
  │                │ INSERT assistant_msg  │              │              │               │            │
  │                ├────────────────────────────────────►│              │               │            │
  │◄── SSE done ───│                     │              │              │               │            │
```

**数据落点**：

| 步骤 | 数据写哪里 |
|------|------------|
| user 消息 | `messages` 表 |
| 检索 | 只读 `knowledge_chunks` |
| assistant 消息 + 轮次产出 | `messages` 表（content + metadata_json：citations、toolCalls、usage、intent） |
| 对话上下文（下轮） | Java 从 `messages` 查 history 再传 Python（**不以 Redis 为准**） |
| 配额 | Redis `quota:team:*:daily_tokens` 递增 |
| 追踪 | OTel → Tempo/Jaeger（可选）或日志关联 |

---

### 7.2 场景二：大文件异步分析（异步链路）

```text
Client       Java           MinIO      PostgreSQL    Kafka       Python Worker
  │ upload      │              │            │            │              │
  ├────────────►│ presign/流式写 ─►│            │            │              │
  │             │ INSERT job PENDING ───────►│            │              │
  │             │ publish AnalysisEvent ─────────────────►│              │
  │◄── 202 ─────│              │            │            │              │
  │             │              │            │            ├─ consume ───►│
  │             │              │◄─ download ─────────────│              │
  │             │              │            │◄─ PROCESSING ────────────│
  │             │              │            │            │   解析特征   │
  │             │              │◄─ put result json ──────│              │
  │             │              │            │◄─ COMPLETED + summary ───│
  │ GET /jobs/id│              │            │            │              │
  ├────────────►│──────────────────────────────────────►│              │
  │◄─ result ───│              │            │            │              │
```

**后续对话引用**：用户问「我上传的 heap 分析结果是什么」→ RouterNode 识别 → 读 `analysis_jobs.result_summary` 或 MinIO 结果文件。

---

### 7.3 场景三：MCP 实时查数（嵌入同步链路）

```text
在 7.1 基础上，RetrieveNode 跳过，走 ToolNode：

Python ToolNode
  → MCP prometheus_query
  → Mock/Real Prometheus API
  → 返回 { "db_connections": 85, "threshold": 100 }
  → SynthesizeNode 生成「当前连接数 85，未超阈值」
```

**数据不持久化到业务表**（可选记入 `messages.metadata_json.tool_calls` 供审计）。

---

### 7.4 异步知识入库链路（完整）

```text
Java: 202 + jobId
Kafka: { eventType: "KNOWLEDGE_INGEST", jobId, documentId, objectKey }
Python Consumer:
  1. PATCH Java internal API: status=PROCESSING
  2. download → parse → chunk → embed
  3. batch insert chunks (internal API)
  4. PATCH status=COMPLETED
失败:
  retry 3 次 → DLQ → status=FAILED + error_message
```

**幂等**：Consumer 以 `jobId` 去重；已 `COMPLETED` 则 skip。

---

## 8. API 设计

### 8.1 对外 API（Java，前缀 `/api/v1`）

| 方法 | 路径 | 说明 | 响应 |
|------|------|------|------|
| POST | `/auth/register` | 注册 | 201 |
| POST | `/auth/login` | 登录 | `{ accessToken, refreshToken }` |
| POST | `/auth/refresh` | 刷新 | 新 token |
| GET | `/agents` | Agent 列表 | 200 |
| POST | `/sessions` | 创建会话 | `{ sessionId }` |
| GET | `/sessions` | 我的会话列表 | 分页 |
| GET | `/sessions/{id}/messages` | 历史消息 | 分页 |
| **POST** | **`/sessions/{id}/chat`** | **SSE 流式聊天** | `text/event-stream` |
| POST | `/knowledge/documents` | 上传知识文档 | 202 + jobId |
| GET | `/knowledge/documents` | 文档列表 | 200 |
| GET | `/knowledge/documents/{id}` | 文档状态 | 200 |
| POST | `/analysis/jobs` | 创建大文件分析任务 | 202 |
| GET | `/analysis/jobs/{id}` | 查询分析结果 | 200 |
| GET | `/admin/users` | Admin 用户列表 | 200 |
| GET | `/actuator/prometheus` | 指标 | Prometheus 抓取 |

#### SSE 事件格式

```text
event: token
data: {"text":"根据"}

event: citation
data: {"chunks":[{"docTitle":"状态码字典","chunkId":"..."}]}

event: done
data: {"messageId":"...","usage":{"promptTokens":120,"completionTokens":80}}

event: error
data: {"code":"LLM_TIMEOUT","message":"..."}
```

### 8.2 内部 API（Java，前缀 `/internal/v1`，Service Token）

| 方法 | 路径 | 调用方 | 说明 |
|------|------|--------|------|
| GET | `/sessions/{id}/messages` | Python | Tool 拉历史 |
| PATCH | `/ingest-jobs/{id}` | Python | 更新入库状态 |
| POST | `/knowledge/chunks/batch` | Python | 批量写入向量块 |
| PATCH | `/analysis-jobs/{id}` | Python | 更新分析任务 |
| GET | `/agents/{id}` | Python | 拉 Agent 配置 |

### 8.3 Python 内部 API（前缀 `/internal/v1`，Service Token）

| 方法 | 路径 | 调用方 | 说明 |
|------|------|--------|------|
| POST | `/chat/stream` | Java | 流式诊断，返回 **NDJSON** 流 |
| POST | `/chat/cancel` | Java | 取消进行中的生成 |
| GET | `/health` | Java/Compose | 健康检查 |

#### 内部流式协议（Java ↔ Python，P8）

| 项 | 约定 |
|----|------|
| Request `Accept` | `application/x-ndjson` |
| Response `Content-Type` | `application/x-ndjson` |
| 格式 | 每行一个 JSON 对象，以 `\n` 分隔 |
| Java 职责 | 按行解析 NDJSON → 转换为对客户端的 SSE |
| Python 职责 | 输出 NDJSON，不使用 SSE 格式 |

```text
{"type":"citation","citations":[...]}
{"type":"token","text":"根据"}
{"type":"done","done":{"usage":{...},"intent":"rag_and_tool"},"citations":[...]}
```

对外客户端仍使用 SSE（见 §8.1），内外协议分离，避免解析歧义。

---

## 9. 跨服务契约与错误模型

### 9.1 统一错误体（对外）

```json
{
  "code": "RATE_LIMITED",
  "message": "Too many requests",
  "traceId": "4bf92f3577b34da6",
  "timestamp": "2026-07-06T10:00:00Z"
}
```

### 9.2 错误码表

| code | HTTP | 说明 |
|------|------|------|
| AUTH_INVALID | 401 | Token 无效 |
| FORBIDDEN | 403 | 无权限 |
| NOT_FOUND | 404 | 资源不存在 |
| RATE_LIMITED | 429 | 限流 |
| QUOTA_EXCEEDED | 429 | 配额用尽 |
| VALIDATION_ERROR | 400 | 参数错误 |
| INGEST_FAILED | 500 | 入库失败 |
| LLM_TIMEOUT | 504 | 模型超时 |
| LLM_RATE_LIMIT | 502 | 上游限流 |
| INTERNAL_ERROR | 500 | 未知错误 |

### 9.3 InternalChatRequest（Java → Python）

```json
{
  "traceId": "4bf92f3577b34da6",
  "sessionId": "uuid",
  "agentConfig": {
    "model": "deepseek-chat",
    "systemPrompt": "...",
    "enableRag": true,
    "enableMcp": true,
    "ragTopK": 5,
    "temperature": 0.2
  },
  "userMessage": "今日早盘商品服务报 STATUS_899 错误是什么原因？",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "userContext": {
    "userId": 1,
    "teamId": 1
  }
}
```

> **约定**：`history` 为最近 N 条 **不含当前轮** `userMessage`；`userMessage` 单独字段传递当前提问。

---

## 10. 安全设计

| 层级 | 措施 |
|------|------|
| 传输 | 生产 HTTPS；内网 Java↔Python 可 mTLS 或 Service JWT |
| 认证 | 对外 JWT；对内 `X-Service-Token` + `aud=ai-plane` |
| SSE 长连接 | 建立连接时校验 JWT；存续期间不中断（见 §6.2） |
| 授权 | Session/Message 校验 userId；Admin API 需 role=ADMIN |
| 知识库 | MVP 按 `team_id` 共享检索；上传记录保留 `user_id` 审计 |
| 限流 | IP + User + Team 三级 |
| 数据 | 密码 BCrypt；API Key 仅环境变量；MinIO bucket 私有 |
| MCP/SQL | 只读白名单；禁止 DDL/DML |
| 审计 | Message + tool_calls 记入 metadata；敏感字段脱敏 |

---

## 11. 可观测性设计

### 11.1 三个黄金信号（每个核心接口）

- **Latency**：`chat_stream_duration_seconds` P50/P99
- **Traffic**：`chat_requests_total`
- **Errors**：`chat_errors_total{code}`

### 11.2 排障路径（验收标准）

> 「昨天 15:00 聊天变慢」

```text
1. Grafana 看 chat P99 是否升高
2. 看 JVM heap/GC、DB connection pool
3. Jaeger/日志用 traceId 抽样慢请求
4. 分段看：Java 转发延迟 vs Python RAG 延迟 vs LLM TTFB
5. 结论写入 Postmortem 模板
```

### 11.3 日志字段规范

```json
{
  "timestamp": "...",
  "level": "INFO",
  "traceId": "...",
  "spanId": "...",
  "service": "control-plane",
  "userId": 1,
  "sessionId": "...",
  "event": "chat.stream.chunk",
  "durationMs": 12
}
```

---

## 12. 非功能需求与容量假设

| 项 | MVP 目标 |
|----|----------|
| 并发 SSE 连接 | 50（单机） |
| 聊天 P99 | < 8s（含 LLM） |
| 文件上传 | 最大 100MB |
| 向量检索 | topK=5，< 200ms |
| Kafka 消费延迟 | P99 < 5min（离线 ingest） |
| 可用性 | 最佳努力；故障演练文档化 |

---

## 13. 部署与本地开发拓扑

### 13.1 Docker Compose 服务清单

```text
services:
  postgres          # 5432, init.sql 启用 pgvector
  redis             # 6379
  kafka + zookeeper # 或 KRaft 单节点
  minio             # 9000 API, 9001 Console
  control-plane     # Java :8080
  ai-plane          # Python :8000
  prometheus        # 9090
  grafana           # 3000
  # optional: jaeger/tempo for traces
```

### 13.2 环境变量（示例）

| 变量 | 服务 | 说明 |
|------|------|------|
| `DATABASE_URL` | Java/Python | PG 连接 |
| `REDIS_URL` | 两者 | |
| `KAFKA_BOOTSTRAP` | 两者 | |
| `MINIO_ENDPOINT` | 两者 | |
| `LLM_API_KEY` | Python | |
| `LLM_BASE_URL` | Python | 兼容端点 |
| `SERVICE_TOKEN_SECRET` | 两者 | 内网调用 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | 两者 | |

### 13.3 仓库结构建议

```text
devops-ai-copilot/
├── control-plane/          # Java Maven
│   └── src/main/java/.../modules/{auth,session,file,admin}
├── ai-plane/               # Python
│   └── app/{api,graph,rag,mcp,consumers}
├── deploy/
│   ├── docker-compose.yml
│   ├── prometheus/
│   └── grafana/dashboards/
├── docs/
│   ├── architecture/
│   └── postmortems/
└── .github/workflows/ci.yml
```

---

## 14. 与 12 周路线的映射

| 周 | 详细设计交付物 | 系统能力闭环 |
|----|----------------|--------------|
| 1 | 鉴权+异常+日志规范 | 可调 API |
| 2 | User/Agent/Session 表 + CRUD | 元数据管理 |
| 3 | Redis 限流 | 防刷 |
| 4 | Java↔Python HTTP + Service Token | 双栈连通 |
| 5 | SSE 端到端 + Message 落库 | **场景一骨架** |
| 6 | LangGraph + rag_and_tool 并行；history 不含本条；流式模式 A | Agent 路由 |
| 7 | pgvector + RetrieveNode（team 过滤） | **场景一 RAG 完整** |
| 8 | MinIO 上传 + 6.8 Analysis Worker 简化解析 | 文件入口 + **场景二骨架** |
| 9 | Kafka ingest pipeline | **异步入库完整** |
| 10 | OTel + Grafana | 可排障 |
| 11 | MCP ToolNode | **场景三完整** |
| 12 | Compose + CI | 可交付 |

**场景二（大文件分析）**：建议在 Week 8~9 与 ingest **共用** MinIO+Kafka 框架，解析器可简化为「提取前 1MB 文本 + 关键字统计」，不必真做完整 heap 分析器。

---

## 15. MVP 范围与刻意不做

### 15.1 MVP 必须交付（最小可演示）

1. 登录 + 创建 Session + SSE 聊天  
2. 上传 PDF 复盘文档 → 异步入库 → RAG 回答 STATUS_899  
3. MCP Mock 查「数据库连接数」  
4. Prometheus 基础大盘 + traceId 日志  
5. `docker compose up` 一键启动  

### 15.2 V2 再做

- 真正 Kibana/Elastic 对接  
- 完整 Heap Dump 解析（Eclipse MAT 级）  
- 多 Team 成员与细粒度 RBAC  
- 独立向量库迁移  
- K8s Helm Chart  

---

## 16. 能力收获对照表（你开发时会练到什么）

| 你在文档里看到的模块 | 练到的工程能力 | 未来用处 |
|----------------------|----------------|----------|
| JWT + 限流 | 安全与流量治理 | 所有 B 端后端 |
| SSE + WebClient 透传 | 流式 HTTP、取消、资源管理 | **AI 后端核心** |
| Java↔Python 契约 | 跨语言微服务协作 | AI 平台团队标准分工 |
| LangGraph | 有状态编排、Checkpoint | Agent 工程化 |
| RAG + pgvector | 检索链路、切块、阈值 | 企业知识助手 |
| Kafka + 幂等消费 | 事件驱动、DLQ | 中大厂后端 |
| MinIO 预签名 | 大文件架构 | 知识库/日志平台 |
| MCP | 标准化 Tool 接入 | 2026 AI 工具生态 |
| OTel + Prometheus | 分布式排障 | 平台/SRE 进阶 |

---

## 17. 收束：系统脉络一图流

```text
【用户问题】「STATUS_899 是什么？现在 DB 连接数正常吗？」
        │
        ▼
【Java 控制面】鉴权 → 限流 → 记 user message → SSE 握持
        │
        ▼
【Python 智能面】LangGraph:
        Router → rag_and_tool 时 RAG ∥ MCP 并行 → LLM 综合
        │
        ▼
【流式返回】Python NDJSON → Java 转 SSE → 用户
        │
        ▼
【持久化】assistant message（含 metadata_json）/ metrics / trace

【用户上传 PDF/日志】
        │
        ▼
【Java】MinIO + 202 + Kafka
        │
        ▼
【Python Worker】解析 → chunk → embed → pgvector
        │
        ▼
【下次 RAG 可召回】
```

---

这份详细设计书可直接作为 **开发前的 Single Source of Truth**。若你下一步需要更「可编码」的粒度，建议在以下三份附录里选一份继续展开（我可以在下一条消息写）：

1. **附录 A**：全部表的 DDL + 索引语句  
2. **附录 B**：LangGraph 各 Node 的伪代码与 State 转换表  
3. **附录 C**：`docker-compose.yml` 服务依赖图与环境变量清单  

你更希望先深化哪一块？