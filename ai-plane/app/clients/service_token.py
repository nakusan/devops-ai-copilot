"""签发内网 Service Token，供 Python → Java Internal API 调用。

双向 audience 约定（与 Java ServiceTokenProvider 对齐）：
- Java → Python：aud=ai-plane（Python deps.verify 校验）
- Python → Java：aud=control-plane（本模块签发；Java Filter 校验 inboundAudience）
"""

from __future__ import annotations

import time

import jwt

from app.config import settings


def issue_service_token() -> str:
    """签发给 control-plane 的出站 Token。"""
    now = int(time.time())
    payload = {
        "sub": settings.service_token_issuer,
        "aud": settings.service_token_outbound_audience,
        "type": "service",
        "iat": now,
        "exp": now + settings.service_token_ttl_seconds,
    }
    return jwt.encode(payload, settings.service_token_secret, algorithm="HS256")
