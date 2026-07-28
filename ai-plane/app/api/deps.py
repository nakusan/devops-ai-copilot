"""FastAPI 依赖：校验内网 Service Token。"""

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import settings


def verify_service_token(
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> None:
    """与 Java ServiceTokenProvider 对齐：HS256 + aud + type=service。"""
    if not x_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID", "message": "缺少 X-Service-Token"},
        )
    try:
        payload = jwt.decode(
            x_service_token,
            settings.service_token_secret,
            algorithms=["HS256"],
            audience=settings.service_token_audience,
            options={"require": ["exp", "aud"]},
        )
        if payload.get("type") != "service":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AUTH_INVALID", "message": "Service Token 类型不正确"},
            )
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_EXPIRED", "message": "Service Token 已过期"},
        ) from ex
    except jwt.PyJWTError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID", "message": "无效的 Service Token"},
        ) from ex


ServiceTokenDep = Annotated[None, Depends(verify_service_token)]
