"""InternalChatRequest / AgentConfig — 与 Java 控制面契约对齐。"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentConfig(BaseModel):
    """诊断 Agent 运行时配置（由 Java 从 agents 表组装）。"""

    model_config = ConfigDict(populate_by_name=True)

    model: str
    system_prompt: str = Field(alias="systemPrompt")
    enable_rag: bool = Field(default=True, alias="enableRag")
    enable_mcp: bool = Field(default=True, alias="enableMcp")
    rag_top_k: int = Field(default=5, alias="ragTopK")
    # None = Agent 未覆盖，回落 settings.rag_score_threshold（唯一默认值来源）
    rag_score_threshold: float | None = Field(default=None, alias="ragScoreThreshold")
    temperature: float = 0.2
    max_history_messages: int = Field(default=20, alias="maxHistoryMessages")
    mcp_servers: list[str] = Field(default_factory=list, alias="mcpServers")
    llm_timeout_seconds: int = Field(default=60, alias="llmTimeoutSeconds")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class UserContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId")
    team_id: int = Field(alias="teamId")


class InternalChatRequest(BaseModel):
    """Java → Python 内部聊天请求。

    约定（P7）：history 为最近 N 条且 **不含本轮**；本轮内容只在 user_message。
    """

    model_config = ConfigDict(populate_by_name=True)

    trace_id: str = Field(alias="traceId")
    session_id: str = Field(alias="sessionId")
    user_message: str = Field(alias="userMessage")
    history: list[ChatMessage] = Field(default_factory=list)
    agent_config: AgentConfig = Field(alias="agentConfig")
    user_context: UserContext = Field(alias="userContext")


class CancelRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    trace_id: str | None = Field(default=None, alias="traceId")


# 供类型检查引用
JsonDict = dict[str, Any]
