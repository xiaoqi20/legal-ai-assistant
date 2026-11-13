from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(
    env_prefix="LAW_", env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True, extra="ignore"
  )
  env: Literal["development", "test", "production"] = "development"
  database_url: SecretStr = SecretStr("postgresql+asyncpg://localhost/law_dev")
  allow_dev_login: bool = False
  cors_origins: list[str] = ["http://localhost:5173"]
  session_hours: int = Field(24, ge=1, le=720)
  deepseek_api_key: SecretStr = SecretStr("")
  deepseek_base_url: str = "https://api.deepseek.com"
  deepseek_model: str = "deepseek-flash"
  embedding_api_key: SecretStr = SecretStr("")
  embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
  embedding_model: str = "text-embedding-v4"
  embedding_dimensions: int = 1536
  ai_timeout_seconds: float = Field(120, ge=1, le=600)
  upstream_read_timeout_seconds: float = Field(30, ge=1, le=120)
  max_concurrent_streams: int = Field(8, ge=1, le=100)
  per_user_requests_per_minute: int = Field(10, ge=1, le=100)
  max_output_tokens: int = Field(2048, ge=64, le=8192)
  max_output_chars: int = Field(32000, ge=100, le=100000)
  max_context_chars: int = Field(16000, ge=1000, le=50000)
  retrieval_top_k: int = Field(6, ge=1, le=20)
  retrieval_min_similarity: float = Field(0.25, ge=0, le=1)
  chunk_chars: int = Field(800, ge=200, le=2000)
  chunk_overlap: int = Field(100, ge=0, le=500)
  max_upload_bytes: int = Field(20 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
  max_document_chars: int = Field(500000, ge=1000, le=2000000)
  max_chunks: int = Field(800, ge=1, le=5000)
  job_lease_seconds: int = Field(180, ge=30, le=600)
  job_timeout_seconds: int = Field(120, ge=10, le=500)
  s3_endpoint_url: str | None = None
  s3_region: str = "us-east-1"
  s3_access_key_id: SecretStr = SecretStr("")
  s3_secret_access_key: SecretStr = SecretStr("")
  s3_bucket: str = "law-private"
  wechat_app_id: str = ""
  wechat_app_secret: SecretStr = SecretStr("")
  input_usd_per_million: Decimal | None = Field(None, ge=0)
  output_usd_per_million: Decimal | None = Field(None, ge=0)

  @model_validator(mode="after")
  def validate_constraints(self):
    if self.env == "production" and self.allow_dev_login:
      raise ValueError("生产环境禁止开发登录和短信 Mock")
    if self.embedding_dimensions != 1536:
      raise ValueError("当前 schema 使用 vector(1536)，请先迁移数据库与索引")
    if self.chunk_overlap >= self.chunk_chars:
      raise ValueError("chunk_overlap 必须小于 chunk_chars")
    if self.job_timeout_seconds >= self.job_lease_seconds:
      raise ValueError("任务超时必须小于租约时间")
    return self


@lru_cache
def get_settings() -> Settings:
  return Settings()
