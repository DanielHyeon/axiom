from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    JWT_SECRET_KEY: str = "super-secret-key-for-local-dev"
    JWT_ALGORITHM: str = "HS256"
    SYNAPSE_API_URL: str = "http://localhost:8003"
    SYNAPSE_SCHEMA_EDIT_BASE: str = "/api/v3/synapse/schema-edit"
    CORE_API_URL: str = "http://localhost:8001"
    SERVICE_TOKEN_ORACLE: str = "local-oracle-token"
    ORACLE_DATASOURCES_JSON: str = (
        '[{"id":"ds_business_main","name":"Business Main DB","type":"postgresql",'
        '"host":"localhost","database":"insolvency_os","status":"active"}]'
    )
    QUERY_HISTORY_DATABASE_URL: str = "postgresql://arkos:arkos@localhost:5432/insolvency_os"

    model_config = ConfigDict(env_file=".env")

settings = Settings()
