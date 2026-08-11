"""AnalysisLookupNode — 查用户最近一次已完成的分析摘要。"""

from __future__ import annotations

import logging
from typing import Any

from app.clients.java_internal_client import java_internal_client
from app.graph.state import DiagnosisState
from app.observability.logging import chat_msg, preview

logger = logging.getLogger(__name__)


async def analysis_lookup_node(state: DiagnosisState) -> dict[str, Any]:
    """查询用户最近一次 heap/文件分析摘要，写入 state.analysis_summary。

    降级策略：Java 不可达或无 COMPLETED job 时返回 None，
    SynthesizeNode / prompt_builder 会提示「暂无已完成的上传分析任务」。
    """
    user_id = None
    try:
        user_ctx = state.get("user_context") or {}
        user_id = user_ctx.get("user_id") or user_ctx.get("userId")
        if user_id is None:
            logger.warning(chat_msg("11.analysis", "status=skip reason=missing_user_id"))
            return {"analysis_summary": None}

        job = await java_internal_client.get_latest_analysis_job(int(user_id))
        if not job:
            logger.info(
                chat_msg("11.analysis", f"userId={user_id} status=empty"),
                extra={"trace_id": state.get("trace_id") or ""},
            )
            return {"analysis_summary": None}

        summary = job.get("resultSummary") or job.get("result_summary")
        job_id = job.get("jobId") or job.get("id")
        logger.info(
            chat_msg(
                "11.analysis",
                f"userId={user_id} jobId={job_id} hasSummary={bool(summary)} "
                f"summary=\"{preview(str(summary) if summary else '')}\"",
            ),
            extra={"trace_id": state.get("trace_id") or ""},
        )
        return {"analysis_summary": summary}
    except Exception:
        logger.exception(
            chat_msg("11.analysis", f"userId={user_id} status=error"),
            extra={"trace_id": state.get("trace_id") or ""},
        )
        return {"analysis_summary": None}
