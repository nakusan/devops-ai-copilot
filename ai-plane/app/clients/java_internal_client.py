"""Java Internal API 客户端（httpx + Service Token）。"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from app.clients.service_token import issue_service_token
from app.config import settings

logger = logging.getLogger(__name__)


class JavaInternalClient:
    """回调 control-plane `/internal/v1/**`。

    写入路径必须走 Java（架构 P2：Python 无 PG 写权限）。
    """

    def __init__(self) -> None:
        self._base = settings.java_internal_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "X-Service-Token": issue_service_token(),
            "Content-Type": "application/json",
        }

    async def get_ingest_job(self, job_id: UUID) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self._base}/internal/v1/ingest-jobs/{job_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def patch_ingest_job(
        self,
        job_id: UUID,
        *,
        status: str,
        error_message: str | None = None,
        retry_count: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"status": status}
        if error_message is not None:
            body["errorMessage"] = error_message
        if retry_count is not None:
            body["retryCount"] = retry_count
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"{self._base}/internal/v1/ingest-jobs/{job_id}",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def post_chunks_batch(
        self, document_id: UUID, chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        body = {"documentId": str(document_id), "chunks": chunks}
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._base}/internal/v1/knowledge/chunks/batch",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_analysis_job(self, job_id: UUID) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self._base}/internal/v1/analysis-jobs/{job_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_latest_analysis_job(self, user_id: int) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self._base}/internal/v1/analysis-jobs",
                headers=self._headers(),
                params={"userId": user_id, "status": "COMPLETED", "latest": "true"},
            )
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            if not resp.content:
                return None
            return resp.json()

    async def list_analysis_jobs(self, user_id: int, *, limit: int = 5) -> list[dict[str, Any]]:
        """列出用户最近分析任务（Agent list_analysis_jobs）。"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self._base}/internal/v1/analysis-jobs",
                headers=self._headers(),
                params={"userId": user_id, "latest": "false", "limit": max(1, min(limit, 20))},
            )
            resp.raise_for_status()
            if not resp.content:
                return []
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return data["items"]
            return []

    async def patch_analysis_job(
        self,
        job_id: UUID,
        *,
        status: str,
        result_summary: str | None = None,
        result_object_key: str | None = None,
        error_message: str | None = None,
        retry_count: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"status": status}
        if result_summary is not None:
            body["resultSummary"] = result_summary
        if result_object_key is not None:
            body["resultObjectKey"] = result_object_key
        if error_message is not None:
            body["errorMessage"] = error_message
        if retry_count is not None:
            body["retryCount"] = retry_count
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"{self._base}/internal/v1/analysis-jobs/{job_id}",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()


java_internal_client = JavaInternalClient()
