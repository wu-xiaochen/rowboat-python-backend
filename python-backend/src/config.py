import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # API Configuration
    provider_base_url: str = Field(default="https://api.siliconflow.cn/v1", env="PROVIDER_BASE_URL")
    provider_api_key: str = Field(default="", env="PROVIDER_API_KEY")
    provider_default_model: str = Field(default="deepseek-ai/DeepSeek-V3.2-Exp", env="PROVIDER_DEFAULT_MODEL")
    provider_copilot_model: str = Field(default="deepseek-ai/DeepSeek-V3.2-Exp", env="PROVIDER_COPILOT_MODEL")

    # Server Configuration
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    debug: bool = Field(False, env="DEBUG")

    # Database Configuration
    database_url: str = Field("sqlite:///./rowboat.db", env="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")

    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_secret: str = Field(..., env="JWT_SECRET")

    # RAG Configuration - 更新为硅基流动的BAAI/bge-m3
    qdrant_url: str = Field("http://localhost:6334", env="QDRANT_URL")  # 修复：使用实际端口 6334
    qdrant_api_key: Optional[str] = Field(None, env="QDRANT_API_KEY")

    # 更新嵌入模型配置为硅基流动的BAAI/bge-m3
    embedding_model: str = Field(default="BAAI/bge-m3", env="EMBEDDING_MODEL")
    embedding_base_url: str = Field(default="https://api.siliconflow.cn/v1", env="EMBEDDING_BASE_URL")
    embedding_api_key: Optional[str] = Field(default=None, env="EMBEDDING_API_KEY")  # 改为可选，会从 PROVIDER_API_KEY 获取
    embedding_model_direct: str = Field(default="BAAI/bge-base-en-v1.5", env="EMBEDDING_MODEL_DIRECT")

    # 知识库配置
    rag_chunk_size: int = Field(1000, env="RAG_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(200, env="RAG_CHUNK_OVERLAP")
    rag_max_chunks: int = Field(500, env="RAG_MAX_CHUNKS")

    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("json", env="LOG_FORMAT")

    # 智能体响应配置 - 解决回复中断问题
    agent_response_timeout: int = Field(60, env="AGENT_RESPONSE_TIMEOUT")  # 减少超时避免卡死
    agent_max_retries: int = Field(3, env="AGENT_MAX_RETRIES")
    agent_request_timeout: int = Field(30, env="AGENT_REQUEST_TIMEOUT")
    agent_response_chunk_size: int = Field(1024, env="AGENT_RESPONSE_CHUNK_SIZE")  # 增大chunk避免中断

    # Composio Configuration
    composio_api_key: Optional[str] = Field(None, env="COMPOSIO_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance - 直接从 .env 文件读取，不传入默认值让 pydantic 自动处理
settings = Settings()

# 如果EMBEDDING_API_KEY未单独设置，使用PROVIDER_API_KEY作为后备
if not settings.embedding_api_key and settings.provider_api_key:
    settings.embedding_api_key = settings.provider_api_key

# 重要：立即设置 OPENAI_API_KEY 环境变量，供 CrewAI 工具和其他依赖使用
# 这必须在任何 CrewAI 工具导入之前设置
if settings.provider_api_key:
    os.environ["OPENAI_API_KEY"] = settings.provider_api_key
    # 同时设置一些 CrewAI 工具可能需要的其他环境变量
    os.environ["OPENAI_API_BASE"] = settings.provider_base_url
    # 注意：某些工具可能需要 OPENAI_MODEL_NAME，但我们使用自定义的 ChatOpenAI 实例

print(f"✅ Settings initialized with embedding model: {settings.embedding_model}")
print(f"✅ Embedding API configured with SiliconFlow")
print(f"✅ OPENAI_API_KEY environment variable set for CrewAI tools")