# DevOps AI Copilot

企业内部研发/运维 **AI 辅助排查平台**后端：控制面（Java / Spring Boot）+ 智能面（Python / FastAPI），通过 RAG、Agent（LangGraph）与 MCP 串联私有知识、异步文件分析与实时监控数据。

> 当前进度：**Phase 2 跨语言流式**（Java SSE ↔ Python Mock NDJSON + Message 落库）。  
> 设计资料：[`docs/`](docs/) · 任务进度：[`docs/implementation-tasks.md`](docs/implementation-tasks.md)

## 仓库结构

```text
control-plane/   Java 21 + Spring Boot 3（公网唯一入口 / SSE 终点）
ai-plane/        Python 3.12 + FastAPI（内网 NDJSON 流；本阶段为 Mock）
deploy/          docker-compose、postgres 分表 SQL、监控占位
docs/            架构与模块设计书（勿删）
```

## 本地快速开始

```bash
# 1) 中间件
make infra-up

# 2) 智能面（Mock 流）
cd ai-plane && uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000

# 3) 控制面（另开终端）
cd control-plane && mvn spring-boot:run
```

| 服务 | 地址 |
|------|------|
| control-plane | http://localhost:8080 |
| ai-plane | http://localhost:8000 |
| PostgreSQL | localhost:5432（copilot/copilot） |
| Redis | localhost:6379 |

两侧 `SERVICE_TOKEN_SECRET` / `copilot.service-token.secret` 必须一致（默认已对齐开发密钥）。

### 联调示例

种子账号：`admin` / `Admin123!`，默认 Agent id=`1`。

```bash
# 登录
TOKEN=$(curl -s http://localhost:8080/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!"}' | jq -r .accessToken)

# 创建 Session
SID=$(curl -s http://localhost:8080/api/v1/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"agentId":1,"title":"排查 STATUS_899"}' | jq -r .id)

# SSE 聊天（--no-buffer 边收边打）
curl -N --no-buffer -X POST "http://localhost:8080/api/v1/sessions/$SID/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{"content":"今日早盘 STATUS_899 是什么原因？","clientMessageId":"demo-1"}'

# 历史消息分页
curl -s "http://localhost:8080/api/v1/sessions/$SID/messages?page=1&size=20" \
  -H "Authorization: Bearer $TOKEN"
```

SSE 事件：`token` / `done` / `error`（本阶段 Python 为 Mock 回显，Week 6 换 LangGraph+真 LLM）。

## 开发约定（生产级基线）

| 层 | 约定 |
|----|------|
| 入口 | 客户端只调 Java；Python 仅内网 |
| 对话真相源 | PostgreSQL `messages`；每轮 Java 传 `history`（不含本条） |
| 流式 | 对内 NDJSON；对外 SSE（Java 转换） |
| Trace | W3C `traceparent`；日志含 `traceId` |
| 密钥 | 环境变量；禁止提交真实 API Key |
| 注释 | **统一使用中文** |
| DB 变更 | 手工维护 [`deploy/postgres/`](deploy/postgres/) |

### Java Filter 链

`TraceId → ServiceToken(/internal) → JwtAuth → RateLimit → Authorization`

### 聊天主路径

鉴权 → 限流 → 配额预检 → 落 user message → WebClient 订 NDJSON → SSE 透传 → 落 assistant → 配额累加；断开则 cancel。

## 常用命令

```bash
make help
make java-compile
make python-sync
make python-lint
make ci-local
```

## 技术栈（摘要）

Java 21 · Spring Boot 3.3 · Spring Security · WebClient · JJWT · MyBatis Plus · PostgreSQL + pgvector · Redis · Kafka · MinIO · FastAPI ·（后续）LangGraph · OpenTelemetry · Prometheus/Grafana
