"""Twin 서비스 설정."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Axiom Twin"
    VERSION: str = "1.0.0"

    DATABASE_URL: str = "postgresql+asyncpg://arkos:arkos@localhost:5432/insolvency_os"
    DATABASE_SCHEMA: str = "twin"

    REDIS_URL: str = "redis://localhost:6379"

    JWT_SECRET_KEY: str = "axiom-dev-secret-key-do-not-use-in-production"
    JWT_ALGORITHM: str = "HS256"

    # 스냅샷 스케줄러 주기 (초)
    SNAPSHOT_INTERVAL_SECONDS: int = 900  # 15분

    model_config = ConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
