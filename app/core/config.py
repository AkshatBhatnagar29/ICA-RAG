from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EMBEDDING_DIMENSION_DEFAULT = 384


class Settings(BaseSettings):
    app_name: str = "Indian Contract Intelligence Agent"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/contract_intelligence",
    )
    redis_url: str = "redis://localhost:6379/0"
    dependency_timeout_seconds: float = 2.0
    max_upload_size_mb: int = Field(default=25, ge=1, le=1024)
    local_storage_root: str = "data/storage"
    processing_version: str = "v1"
    ocr_enabled: bool = True
    ocr_executable: str = "tesseract"
    ocr_timeout_seconds: float = Field(default=30.0, ge=1, le=300)
    ocr_min_text_chars: int = Field(default=20, ge=1, le=1000)
    libreoffice_executable: str = "libreoffice"
    processing_timeout_seconds: float = Field(default=120.0, ge=1, le=600)
    chunk_target_tokens: int = Field(default=600, ge=1)
    chunk_soft_max_tokens: int = Field(default=1000, ge=1)
    chunk_hard_max_tokens: int = Field(default=1500, ge=1)
    chunk_overlap_tokens: int = Field(default=40, ge=0)
    chunk_refinement_mode: str = Field(default="base", pattern=r"^(base|refined)$")
    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dimension: int = Field(default=EMBEDDING_DIMENSION_DEFAULT, ge=1)
    embedding_batch_size: int = Field(default=32, ge=1, le=1024)
    embedding_threads: int = Field(default=4, ge=1, le=64)
    embedding_cache_path: str = "data/model-cache"
    retrieval_rrf_k: int = Field(default=60, ge=1, le=1000)
    reranker_enabled: bool = False
    reranker_model: str = "jinaai/jina-reranker-v1-tiny-en"
    reranker_model_version: str = "jina-reranker-v1-tiny-en"
    reranker_cache_path: str = "data/model-cache/reranker"
    reranker_candidate_k: int = Field(default=40, ge=1, le=200)
    reranker_top_k: int = Field(default=5, ge=1, le=100)
    reranker_batch_size: int = Field(default=8, ge=1, le=128)
    reranker_max_length: int = Field(default=512, ge=32, le=8192)
    reranker_threads: int = Field(default=1, ge=1, le=64)
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = Field(default=30.0, ge=1, le=300)
    groq_max_retries: int = Field(default=2, ge=0, le=5)
    generation_max_context_tokens: int = Field(default=6000, ge=256, le=100000)
    generation_top_k: int = Field(default=10, ge=1, le=100)
    generation_max_output_tokens: int = Field(default=1200, ge=64, le=10000)
    generation_min_reranker_score: float = -0.3
    auth_jwt_secret: str = Field(default="", repr=False)
    auth_issuer: str = "icia"
    auth_audience: str = "icia-api"
    auth_access_token_minutes: int = Field(default=30, ge=1, le=1440)
    auth_bootstrap_token: str | None = Field(default=None, repr=False)
    auth_password_min_length: int = Field(default=12, ge=8, le=256)
    hnsw_m: int = Field(default=16, ge=4, le=100)
    hnsw_ef_construction: int = Field(default=64, ge=4, le=1000)

    @model_validator(mode="after")
    def require_production_auth_secret(self) -> Self:
        if self.app_env.lower() in {"production", "prod"} and len(self.auth_jwt_secret) < 32:
            raise ValueError("AUTH_JWT_SECRET must be at least 32 characters in production")
        if self.app_env.lower() in {"production", "prod"} and self.auth_bootstrap_token:
            raise ValueError("AUTH_BOOTSTRAP_TOKEN must not be configured in production")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
