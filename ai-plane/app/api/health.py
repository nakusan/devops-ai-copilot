"""健康检查与就绪探针（内网可访问）。"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """存活探测响应体 —— 字段保持精简，便于负载均衡探活。"""

    status: str = Field(examples=["ok"])
    service: str = Field(default="ai-plane")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
