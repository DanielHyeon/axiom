from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Axiom Core"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # DB configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    
    # Redis configuration
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT Auth
    JWT_SECRET_KEY: str = "axiom-dev-secret-key-do-not-use-in-production"
    
    # LLM Defaults
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4o"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
