"""AnalysisLookupNode — MVP 占位（Phase 4 接 Java analysis_jobs）。"""

from typing import Any

from app.graph.state import DiagnosisState


async def analysis_lookup_node(state: DiagnosisState) -> dict[str, Any]:
    """查询用户最近一次 heap/文件分析摘要。

    TODO(Phase-4/W8): Java internal API 查 analysis_job — Analysis Worker + Java API 未就绪
    — 实现 java_client.get_latest_analysis_job(user_id, status=COMPLETED)
    """
    # 降级：无真实 job 时 summary=None，Synthesize 会在 prompt 中说明无分析结果
    return {"analysis_summary": None}
