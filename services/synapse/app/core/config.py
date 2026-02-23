from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    JWT_SECRET_KEY: str = "super-secret-key-for-local-dev"
    JWT_ALGORITHM: str = "HS256"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    SERVICE_TOKEN_ORACLE: str = "local-oracle-token"
    SCHEMA_EDIT_DATABASE_URL: str = "postgresql://arkos:arkos@localhost:5432/insolvency_os"
    # Extraction NER (Phase S6): 비어 있으면 Mock 반환
    OPENAI_API_KEY: str = ""
    EXTRACTION_LLM_MODEL: str = "gpt-4o-mini"
    EXTRACTION_LLM_ENABLED: bool = False
    # Ontology Ingest (Phase S7): 비어 있으면 소비 비활성화
    REDIS_URL: str = ""

    model_config = ConfigDict(env_file=".env")

settings = Settings()
