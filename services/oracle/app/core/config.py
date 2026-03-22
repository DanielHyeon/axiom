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

    # ── Semantic Contract Cache (Sprint 3) ──
    SEMANTIC_CACHE_TTL: int = 1800             # 시멘틱 계약 캐시 TTL (초, 기본 30분)
    SEMANTIC_CACHE_ENABLED: bool = True        # False면 항상 Synapse 직접 호출

    # ── Sprint 1: 시멘틱 계약 사후 검증 모드 ──
    # "log_only" = 위반 기록만 (항상 통과)
    # "warn"    = 위반 경고 포함하되 통과
    # "enforce" = BLOCK 위반 시 SQL 실행 차단
    SEMANTIC_GUARD_MODE: str = "warn"

    # ── Feature Flags (#12, #13 P1-2) ──
    ENABLE_QUALITY_GATE: bool = True          # True면 LLM 기반 품질 게이트 활성화, False면 항상 APPROVE
    ENABLE_VALUE_MAPPING: bool = True         # True면 Value Mapping 파이프라인 활성화

    # ── Enum Cache Bootstrap (#8 P1-1) ──
    ENUM_CACHE_ENABLED: bool = True           # True면 서비스 시작 시 enum 캐시 초기화
    ENUM_CACHE_MAX_VALUES: int = 100          # 100개 이하 고유값만 캐시 (초과 시 enum 아님)
    ENUM_CACHE_MAX_COLUMNS: int = 2000        # information_schema 스캔 대상 최대 컬럼 수
    ENUM_CACHE_TARGET_SCHEMA: str = "public"  # 스캔 대상 PostgreSQL 스키마

    # ── Text2SQL Validity Bootstrap (#P4-16) ──
    VALIDITY_BOOTSTRAP_ENABLED: bool = True            # True면 유효성 부트스트랩 활성화
    VALIDITY_BOOTSTRAP_CONCURRENCY: int = 6            # Synapse API 동시 호출 수
    VALIDITY_BOOTSTRAP_TARGET_SCHEMA: str = "public"   # 스캔 대상 PostgreSQL 스키마

    # ── Query Similarity (#P4-17) ──
    ENABLE_QUERY_SIMILARITY: bool = True
    QUERY_SIMILARITY_HIGH_THRESHOLD: float = 0.95
    QUERY_SIMILARITY_MID_THRESHOLD: float = 0.80
    QUERY_SIMILARITY_MAX_STORE: int = 10000

    # ── C-Pipeline (#P4 Phase 1-2) ──
    ENABLE_C_PIPELINE: bool = True            # True면 C-Pipeline(탐색→수렴→탈출) 활성화, False면 기존 ReAct 유지
    ENABLE_HYDE: bool = True                  # True면 HyDE(가상 SQL) 검색 다양성 활성화
    ENABLE_TABLE_RERANKING: bool = True       # True면 LLM 기반 테이블 리랭킹 활성화
    ENABLE_CONVERSATION_STATE: bool = True    # True면 멀티턴 대화 컨텍스트 유지

    model_config = ConfigDict(env_file=".env")

settings = Settings()
