"""应用配置（pydantic-settings）。"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量加载配置。密钥禁止写入源码仓库。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "ai-plane"
    # 必须与 Java copilot.service-token.secret 一致
    service_token_secret: str = "dev-only-service-token-secret-change-me"
    service_token_audience: str = "ai-plane"

    # --- LLM（模式 A：图外流式）---
    # mock：无 Key 时自动降级；openai：OpenAI 兼容 API
    llm_mode: Literal["mock", "openai"] = "mock"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 60
    # Mock 流每个 token 间隔（毫秒），便于观察 SSE
    llm_mock_delay_ms: int = 30
    # Mock 按多少字符切一片
    llm_mock_chunk_size: int = 2

    # --- Embedding / RAG（W7）---
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1536
    embedding_model_version: str = "v1"
    database_readonly_url: str | None = None

    # --- Java Internal API（Analysis 节点 TODO 预留）---
    java_internal_base_url: str = "http://control-plane:8080"

    def effective_llm_mode(self) -> Literal["mock", "openai"]:
        """无 API Key 时强制 mock，保证 CI/本机无密钥也能跑通。"""
        if self.llm_mode == "openai" and self.llm_api_key:
            return "openai"
        return "mock"

    def effective_embedding_api_key(self) -> str | None:
        """Embedding 优先用独立 Key，否则复用 LLM Key。"""
        return self.embedding_api_key or self.llm_api_key


settings = Settings()
