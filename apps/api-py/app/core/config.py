from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(WORKSPACE_ROOT / ".env")


def normalize_database_url(value: str | None) -> str:
    if not value:
        raise ValueError("DATABASE_URL is required")
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(WORKSPACE_ROOT / ".env"), extra="ignore")

    app_name: str = "zhujian-planning-api"
    port: int = Field(default=8787, alias="PORT")
    database_url: str = Field(alias="DATABASE_URL")
    pg_schema: str = Field(default="public", alias="PGSCHEMA")
    pg_sslmode: str = Field(default="disable", alias="PGSSLMODE")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/1", alias="CELERY_RESULT_BACKEND")

    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="zhujian", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")
    storage_mode: str = Field(default="auto", alias="STORAGE_MODE")

    model_gateway_url: str | None = Field(default=None, alias="MODEL_GATEWAY_URL")
    model_gateway_api_key: str | None = Field(default=None, alias="MODEL_GATEWAY_API_KEY")
    model_gateway_timeout: float = Field(default=8.0, alias="MODEL_GATEWAY_TIMEOUT")
    ai_mode: str = Field(default="local_rules", alias="AI_MODE")
    libreoffice_path: str | None = Field(default=None, alias="LIBREOFFICE_PATH")

    @property
    def sqlalchemy_url(self) -> str:
        return normalize_database_url(self.database_url)

    @property
    def storage_root(self) -> Path:
        return WORKSPACE_ROOT / "storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
