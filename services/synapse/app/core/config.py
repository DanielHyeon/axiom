from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    JWT_SECRET_KEY: str = "super-secret-key-for-local-dev"
    JWT_ALGORITHM: str = "HS256"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    SERVICE_TOKEN_ORACLE: str = "local-oracle-token"

    class Config:
        env_file = ".env"

settings = Settings()
