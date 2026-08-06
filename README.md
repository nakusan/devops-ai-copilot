# DevOps AI Copilot

企业内部研发/运维 **AI 辅助排查平台**后端：控制面（Java / Spring Boot）+ 智能面（Python / FastAPI），通过 RAG、Agent（LangGraph）与 MCP 串联私有知识、异步文件分析与实时监控数据。

> 当前进度：**Phase 6 / W12 容器化交付**（多阶段 Dockerfile + Compose 全栈 + CI）。  
> 设计资料：[`docs/`](docs/) · 任务进度：[`docs/implementation-tasks.md`](docs/implementation-tasks.md)

## 仓库结构

```text
control-plane/   Java 21 + Spring Boot 3（公网唯一入口 / SSE 终点）
ai-plane/        Python 3.12 + FastAPI（内网 NDJSON 流 + LangGraph / MCP）
deploy/          docker-compose、postgres SQL、Prometheus/Grafana
docs/            架构与模块设计书
.github/         CI（编译测试 / Ruff / Pytest / Docker build）
```

## 本地快速开始

### 方式 A：全栈一键（推荐演示）

```bash
cp deploy/.env.example deploy/.env   # 可按需改密钥 / LLM
make stack-up                        # 中间件 + control-plane + ai-plane + worker
```

| 服务 | 地址 |
|------|------|
| control-plane | http://localhost:8080 |
| ai-plane | http://localhost:8000 |
| Grafana | http://localhost:3000（admin/admin） |
| Prometheus | http://localhost:9090（全栈用服务名抓取 `control-plane`/`ai-plane`） |
| MinIO Console | http://localhost:9001 |

停止：`make stack-down`。

> 工程化约定（学习向）：RAG 使用只读库账号 `copilot_ro`；CI 含 Ruff + Pyright + 测试 + 镜像构建；监控在 Compose 网络内用服务发现。

### 方式 B：中间件进 Docker，应用本机跑（日常开发）

```bash
make infra-up

# 智能面 HTTP
cd ai-plane && uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000

# 独立 Worker（另开终端）
export KAFKA_BOOTSTRAP=localhost:9092
uv run python -m app.worker

# 控制面（另开终端）
cd control-plane && mvn spring-boot:run
```

Kafka：**宿主机**用 `localhost:9092`，**Compose 内应用**用 `kafka:29092`（双监听，见 `deploy/docker-compose.yml` 注释）。

两侧 `SERVICE_TOKEN_SECRET` 必须一致（默认已对齐开发密钥）。

### 联调示例

种子账号：`admin` / `Admin123!`，默认 Agent id=`1`。

```bash
TOKEN=$(curl -s http://localhost:8080/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!"}' | jq -r .accessToken)

SID=$(curl -s http://localhost:8080/api/v1/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"agentId":1,"title":"排查 STATUS_899"}' | jq -r .id)

curl -N --no-buffer -X POST "http://localhost:8080/api/v1/sessions/$SID/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{"content":"今日早盘 STATUS_899 是什么原因？","clientMessageId":"demo-1"}'
```

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
make stack-up / stack-down
make infra-up / infra-down
make java-test
make python-lint python-test
make ci-local
```

## 技术栈（摘要）

Java 21 · Spring Boot 3.3 · Spring Security · WebClient · JJWT · MyBatis Plus · PostgreSQL + pgvector · Redis · Kafka · MinIO · FastAPI · LangGraph · MCP · OpenTelemetry · Prometheus/Grafana · Docker Compose · GitHub Actions
