"""文本采样：只读文件前 N 字节（MVP 降低内存与解析成本）。"""

from __future__ import annotations

from pathlib import Path


def sample_text(path: Path, max_bytes: int) -> str:
    """读取前 max_bytes，用 replace 解码——二进制 hprof 也能得到可正则的噪声文本。"""
    raw = path.read_bytes()[:max_bytes]
    return raw.decode("utf-8", errors="replace")
