# 智能面（AI Plane）

FastAPI 聊天编排 + 独立 Kafka Worker（知识入库 / 大文件分析）。

```bash
uv sync --extra dev
# 密钥需与 control-plane 的 copilot.service-token.secret 一致
export SERVICE_TOKEN_SECRET=dev-only-service-token-secret-change-me

# 1) HTTP 服务（聊天 / LangGraph）
uv run uvicorn app.main:app --reload --port 8000

# 2) 异步 Worker（另开终端；依赖 Kafka）
export KAFKA_BOOTSTRAP=localhost:9092
uv run python -m app.worker
# 或：uv run ai-plane-worker
# 仅跑某一类：WORKER_ROLES=knowledge 或 WORKER_ROLES=analysis
```

内部接口：

- `POST /internal/v1/chat/stream`（`application/x-ndjson`）
- `POST /internal/v1/chat/cancel`
