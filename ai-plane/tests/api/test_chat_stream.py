"""内部聊天流式接口测试（Mock + Service Token）。"""

import time

import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def _issue_service_token(*, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "sub": "control-plane",
        "aud": settings.service_token_audience,
        "type": "service",
        "iat": now - 10,
        "exp": now - 5 if expired else now + 300,
    }
    return jwt.encode(payload, settings.service_token_secret, algorithm="HS256")


def _sample_body() -> dict:
    return {
        "traceId": "abc123",
        "sessionId": "11111111-1111-1111-1111-111111111111",
        "userMessage": "你好世界",
        "history": [],
        "agentConfig": {
            "model": "deepseek-chat",
            "systemPrompt": "test",
            "enableRag": True,
            "enableMcp": True,
            "ragTopK": 5,
            "temperature": 0.2,
        },
        "userContext": {"userId": 1, "teamId": 1},
    }


def test_stream_rejects_missing_token() -> None:
    resp = client.post("/internal/v1/chat/stream", json=_sample_body())
    assert resp.status_code == 401


def test_stream_returns_token_and_done() -> None:
    # 测试加速：临时减小 delay（settings 是模块级单例，测完不恢复也影响有限）
    settings.llm_mock_delay_ms = 0
    token = _issue_service_token()
    with client.stream(
        "POST",
        "/internal/v1/chat/stream",
        json=_sample_body(),
        headers={"X-Service-Token": token},
    ) as resp:
        assert resp.status_code == 200
        lines = [ln for ln in resp.iter_lines() if ln]
    assert len(lines) >= 2
    import json

    events = [json.loads(ln) for ln in lines]
    types = [e["type"] for e in events]
    assert "token" in types
    assert types[-1] in {"done", "error"}
    if types[-1] == "done":
        assert "usage" in events[-1]["done"]


def test_cancel_endpoint() -> None:
    token = _issue_service_token()
    resp = client.post(
        "/internal/v1/chat/cancel",
        json={"sessionId": "11111111-1111-1111-1111-111111111111"},
        headers={"X-Service-Token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
