"""Knowledge 入库事件（与 Java KnowledgeIngestEvent 对齐）。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeIngestEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: UUID | None = Field(default=None, alias="eventId")
    event_type: Literal["KNOWLEDGE_INGEST"] = Field(default="KNOWLEDGE_INGEST", alias="eventType")
    job_id: UUID = Field(alias="jobId")
    document_id: UUID = Field(alias="documentId")
    object_key: str = Field(alias="objectKey")
    mime_type: str | None = Field(default=None, alias="mimeType")
    user_id: int = Field(alias="userId")
    team_id: int = Field(alias="teamId")
    trace_id: str | None = Field(default=None, alias="traceId")
    created_at: datetime | None = Field(default=None, alias="createdAt")
