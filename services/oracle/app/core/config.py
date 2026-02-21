from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    JWT_SECRET_KEY: str = "super-secret-key-for-local-dev"
    JWT_ALGORITHM: str = "HS256"
    SYNAPSE_API_URL: str = "http://localhost:8003"
    SERVICE_TOKEN_ORACLE: str = "local-oracle-token"

    class Config:
        env_file = ".env"

settings = Settings()
