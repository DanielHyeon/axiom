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

    # ── Redis (LLM 시맨틱 캐시용) ──
    REDIS_URL: str = "redis://localhost:6379"
    LLM_CACHE_TTL: int = 3600                  # LLM 캐시 기본 TTL (초)
    LLM_CACHE_ENABLED: bool = True             # False면 캐시 조회/저장 건너뜀

    # ── Feature Flags (#12, #13 P1-2) ──
    ENABLE_QUALITY_GATE: bool = True          # True면 LLM 기반 품질 게이트 활성화, False면 항상 APPROVE
    ENABLE_VALUE_MAPPING: bool = True         # True면 Value Mapping 파이프라인 활성화

    # ── Enum Cache Bootstrap (#8 P1-1) ──
    ENUM_CACHE_ENABLED: bool = True           # True면 서비스 시작 시 enum 캐시 초기화
    ENUM_CACHE_MAX_VALUES: int = 100          # 100개 이하 고유값만 캐시 (초과 시 enum 아님)
    ENUM_CACHE_MAX_COLUMNS: int = 2000        # information_schema 스캔 대상 최대 컬럼 수
    ENUM_CACHE_TARGET_SCHEMA: str = "public"  # 스캔 대상 PostgreSQL 스키마

    model_config = ConfigDict(env_file=".env")

settings = Settings()
