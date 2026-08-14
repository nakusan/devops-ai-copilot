"""MinIO 下载封装（同步 SDK，经 to_thread 供 async 调用）。

不打日志：objectKey / 结果大小已由调用方的 [INGEST] 步骤日志覆盖。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from minio import Minio

from app.config import settings


def _client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def download_to_temp(object_key: str) -> Path:
    """流式下载到临时文件，避免大文件整文件进内存。

    调用方负责处理完后 unlink。
    """
    suffix = Path(object_key).suffix or ".bin"
    client = _client()
    response = None
    # delete=False：返回 Path 给调用方异步处理后再 unlink；不能用 with（退出即关闭路径失效）
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
    try:
        response = client.get_object(settings.minio_bucket, object_key)
        for chunk in response.stream(32 * 1024):
            tmp.write(chunk)
        tmp.flush()
        return Path(tmp.name)
    finally:
        tmp.close()
        if response is not None:
            response.close()
            response.release_conn()


def upload_bytes(object_key: str, data: bytes, content_type: str = "application/json") -> None:
    """上传小结果文件（如 analysis result.json）。"""
    from io import BytesIO

    client = _client()
    client.put_object(
        settings.minio_bucket,
        object_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
