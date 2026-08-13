"""应用配置（pydantic-settings）。"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量加载配置。密钥禁止写入源码仓库。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "ai-plane"
    # 必须与 Java copilot.service-token.secret 一致
    service_token_secret: str = "dev-only-service-token-secret-change-me"
    # 入站校验：Java → Python 时 Token 的 aud（本服务身份）
    service_token_audience: str = "ai-plane"
    # 出站签发：Python → Java 时 Token 的 aud（对端身份）
    service_token_outbound_audience: str = "control-plane"
    # 签发时的 sub（调用方身份）
    service_token_issuer: str = "ai-plane"
    service_token_ttl_seconds: int = 300

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

    # --- Java Internal API（Python → Java 回调，Phase 4）---
    java_internal_base_url: str = "http://localhost:8080"

    # --- Kafka / MinIO（未配置 bootstrap 时不启动 Consumer，聊天仍可用）---
    kafka_bootstrap: str | None = None
    kafka_knowledge_topic: str = "knowledge.ingest.v1"
    kafka_knowledge_dlq: str = "knowledge.ingest.dlq.v1"
    kafka_analysis_topic: str = "analysis.ingest.v1"
    kafka_analysis_dlq: str = "analysis.ingest.dlq.v1"
    kafka_ingest_group: str = "ai-plane-ingest-v1"
    kafka_analysis_group: str = "ai-plane-analysis-v1"
    ingest_max_retries: int = 3

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "devops-copilot"
    minio_secure: bool = False

    # --- RAG 切块（W9）---
    chunk_size: int = 2000  # 约 512 tokens（字符近似）
    chunk_overlap: int = 200
    embedding_batch_size: int = 32

    # --- Analysis MVP（W8）---
    analysis_sample_bytes: int = 1_048_576  # 前 1MB

    # --- 独立 Worker（与 FastAPI 分进程）---
    # knowledge / analysis，逗号分隔；空或未设则两者都启
    worker_roles: str = "knowledge,analysis"

    # --- Observability（W10 / Phase 7）---
    otel_service_name: str = "ai-plane"
    # 空则不导出 OTLP，仅进程内 Tracer（日志关联）
    otel_exporter_otlp_endpoint: str | None = None
    # Resource 属性：Grafana 按环境 / 版本筛选
    service_version: str = "0.1.0"
    deploy_env: str = "dev"
    # 采样率：1.0=全采样；<1 时用 TraceIdRatioBased（ParentBased 尊重上游决策）
    otel_sample_rate: float = 1.0

    # --- Chat HTTP 后端（W11：默认走 LangGraph orchestrator；可回退 mock）---
    chat_backend: Literal["orchestrator", "mock"] = "orchestrator"

    # --- MCP（W11）---
    mcp_enabled: bool = True
    mcp_default_timeout_seconds: float = 5.0

    def effective_llm_mode(self) -> Literal["mock", "openai"]:
        """无 API Key 时强制 mock，保证 CI/本机无密钥也能跑通。"""
        if self.llm_mode == "openai" and self.llm_api_key:
            return "openai"
        return "mock"

    def effective_embedding_api_key(self) -> str | None:
        """Embedding 优先用独立 Key，否则复用 LLM Key。"""
        return self.embedding_api_key or self.llm_api_key


settings = Settings()
