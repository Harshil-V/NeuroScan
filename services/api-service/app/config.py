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
    # Public URL browsers use to fetch presigned URLs. Inside Docker the S3
    # client talks to minio:9000 (internal), but browsers need localhost:9000.
    # Override with MINIO_PUBLIC_URL in docker-compose; defaults to minio_endpoint
    # so local-only setups (no Docker) work without extra config.
    minio_public_url: str = ""
    # PHI scanner salt for value hashing. Override DEID_HASH_SALT in production.
    # Never log this value; never return it via API.
    deid_hash_salt: str = "neuroscan-dev-salt"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
