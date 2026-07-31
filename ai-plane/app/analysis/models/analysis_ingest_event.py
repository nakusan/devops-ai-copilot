"""Analysis 入库事件模型（与 Java AnalysisIngestEvent camelCase 对齐）。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalysisIngestEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: UUID | None = Field(default=None, alias="eventId")
    event_type: Literal["ANALYSIS_INGEST"] = Field(default="ANALYSIS_INGEST", alias="eventType")
    job_id: UUID = Field(alias="jobId")
    user_id: int = Field(alias="userId")
    team_id: int | None = Field(default=None, alias="teamId")
    object_key: str = Field(alias="objectKey")
    file_type: str = Field(alias="fileType")
    trace_id: str | None = Field(default=None, alias="traceId")
    created_at: datetime | None = Field(default=None, alias="createdAt")
