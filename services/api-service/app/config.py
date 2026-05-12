from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_port: int = 8000
    database_url: str = Field(
        default="postgresql+psycopg://neuroscan:neuroscan@localhost:5432/neuroscan",
    )
    orthanc_url: str = "http://localhost:8042"
    orthanc_user: str = "orthanc"
    orthanc_password: str = "orthanc"
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "neuroscan"
    minio_region: str = "us-east-1"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
