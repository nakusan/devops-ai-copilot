"""Service Token 双向 audience 约定。"""

import jwt

from app.clients.service_token import issue_service_token
from app.config import settings


def test_outbound_token_targets_control_plane():
    token = issue_service_token()
    payload = jwt.decode(
        token,
        settings.service_token_secret,
        algorithms=["HS256"],
        audience=settings.service_token_outbound_audience,
        options={"require": ["exp", "aud"]},
    )
    assert payload["aud"] == "control-plane" or (
        isinstance(payload["aud"], list) and "control-plane" in payload["aud"]
    )
    assert payload["sub"] == settings.service_token_issuer
    assert payload["type"] == "service"


def test_outbound_token_rejected_as_inbound_to_ai_plane():
    """出站 Token 的 aud 不是 ai-plane，不能冒充 Java→Python 入站。"""
    token = issue_service_token()
    try:
        jwt.decode(
            token,
            settings.service_token_secret,
            algorithms=["HS256"],
            audience=settings.service_token_audience,
            options={"require": ["exp", "aud"]},
        )
        raise AssertionError("expected InvalidAudienceError")
    except jwt.InvalidAudienceError:
        pass
