from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import list as List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://alina:alina123@postgres:5432/alina_pharma"
    REDIS_URL: str = "redis://redis:6379/0"
    SECRET_KEY: str = "change-me"
    ENCRYPTION_KEY: str = "change-me-32bytes-base64-key======"
    S3_ENDPOINT_URL: str = "https://s3.selectel.ru"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "alina-pharma-labels"
    S3_REGION: str = "ru-1"
    CORS_ORIGINS: str = "http://localhost:5173"
    INITIAL_ADMIN_PASSWORD: str = "Admin123!"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
