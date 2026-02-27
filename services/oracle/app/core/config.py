from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    # Core와 동일한 값 사용 시 Core가 발급한 JWT 검증 가능 (O3 Core 연동)
    JWT_SECRET_KEY: str = "axiom-dev-secret-key-do-not-use-in-production"
    JWT_ALGORITHM: str = "HS256"
    SYNAPSE_API_URL: str = "http://localhost:8003"
    SYNAPSE_SCHEMA_EDIT_BASE: str = "/api/v3/synapse/schema-edit"
    CORE_API_URL: str = "http://localhost:8001"
    SERVICE_TOKEN_ORACLE: str = "local-oracle-token"
    WEAVER_QUERY_API_URL: str = "http://localhost:8001/api/query"
    WEAVER_BEARER_TOKEN: str = ""
    ORACLE_SQL_EXECUTION_MODE: str = "hybrid"  # mock | hybrid | weaver | direct
    ORACLE_SQL_EXECUTION_TIMEOUT_SEC: int = 15
    ORACLE_DATASOURCES_JSON: str = "[]"
    QUERY_HISTORY_DATABASE_URL: str = "postgresql://arkos:arkos@localhost:5432/insolvency_os"
    # Weaver Insight auto-ingest (P1-B).  Leave WEAVER_INSIGHT_TOKEN empty to disable.
    WEAVER_INSIGHT_URL: str = "http://weaver:8001/api/insight/logs"
    WEAVER_INSIGHT_TOKEN: str = ""   # must match WEAVER_INSIGHT_SERVICE_TOKEN in Weaver

    model_config = ConfigDict(env_file=".env")

settings = Settings()
