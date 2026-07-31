"""MVP 关键字 / 异常类名统计（设计 6.8 §4）。"""

from __future__ import annotations

import re
from typing import Any

KEYWORDS: dict[str, str] = {
    "OOM": r"OutOfMemoryError|java\.lang\.OutOfMemoryError",
    "FULL_GC": r"Full GC|Pause Full",
    "EXCEPTION": r"Exception|ERROR",
}


def analyze_text_sample(text: str, file_type: str) -> dict[str, Any]:
    counts = {k: len(re.findall(p, text)) for k, p in KEYWORDS.items()}
    # dict.fromkeys 保序去重，取前 5 个常见异常类名
    top_exceptions = list(dict.fromkeys(re.findall(r"([a-zA-Z0-9_.]+Exception)", text)))[:5]
    return {
        "file_type": file_type,
        "sample_bytes": len(text.encode("utf-8", errors="replace")),
        "keyword_counts": counts,
        "top_exceptions": top_exceptions,
    }


def build_summary(parsed: dict[str, Any]) -> str:
    c = parsed["keyword_counts"]
    return (
        f"文件类型: {parsed['file_type']}。\n"
        f"采样分析（前 {parsed['sample_bytes']} 字节）：\n"
        f"- OOM 相关: {c['OOM']} 处\n"
        f"- Full GC: {c['FULL_GC']} 处\n"
        f"- Exception/ERROR: {c['EXCEPTION']} 处\n"
        f"- 常见异常: {', '.join(parsed['top_exceptions']) or '无'}"
    )
