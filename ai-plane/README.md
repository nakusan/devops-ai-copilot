# 智能面（AI Plane）

FastAPI AI 编排服务。Phase 2：Mock NDJSON 流 + Service Token。

```bash
uv sync --extra dev
# 密钥需与 control-plane 的 copilot.service-token.secret 一致
export SERVICE_TOKEN_SECRET=dev-only-service-token-secret-change-me
uv run uvicorn app.main:app --reload --port 8000
```

内部接口：

- `POST /internal/v1/chat/stream`（`application/x-ndjson`）
- `POST /internal/v1/chat/cancel`
