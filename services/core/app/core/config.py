from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Axiom Core"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # DB configuration
    DATABASE_URL: str = "postgresql+asyncpg://arkos:arkos@localhost:5432/insolvency_os"
    
    # Redis configuration
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT Auth (07_security/auth-model.md)
    JWT_SECRET_KEY: str = "axiom-dev-secret-key-do-not-use-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_SECONDS: int = 900  # 15 min
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    
    # LLM Defaults
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4o"
    LLM_COMPLETION_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_TIMEOUT_SECONDS: float = 20.0

    # Synapse gateway proxy
    SYNAPSE_BASE_URL: str = "http://localhost:8002"
    SYNAPSE_SERVICE_TOKEN: str = "local-oracle-token"

    MCP_EXECUTE_PATH: str = "/tools/execute"
    MCP_TIMEOUT_SECONDS: float = 15.0

    # Seed dev user (only when SEED_DEV_USER=1 and no users exist)
    SEED_DEV_USER: bool = False
    SEED_DEV_EMAIL: str = "admin@local.axiom"
    SEED_DEV_PASSWORD: str = "admin"

    model_config = ConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
