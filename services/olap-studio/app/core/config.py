"""OLAP Studio 설정 — 환경 변수 기반 구성."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    """OLAP Studio 환경 설정.

    .env 파일 또는 환경 변수에서 값을 읽는다.
    """
    ENVIRONMENT: str = "development"

    # 인증
    JWT_SECRET_KEY: str = "axiom-dev-secret-key-do-not-use-in-production"
    JWT_ALGORITHM: str = "HS256"

    # PostgreSQL — OLAP 스키마 전용
    DATABASE_URL: str = "postgresql://arkos:arkos@localhost:5432/insolvency_os"

    # Neo4j — 리니지 그래프 조회용
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Redis — 이벤트 버스 + 캐싱
    REDIS_URL: str = ""

    # OpenAI — AI 큐브 생성, NL2SQL
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Airflow 연동
    AIRFLOW_BASE_URL: str = ""
    AIRFLOW_USER: str = "airflow"
    AIRFLOW_PASSWORD: str = "airflow"

    # 쿼리 실행 제한
    QUERY_TIMEOUT_SEC: int = 30
    MAX_RESULT_ROWS: int = 1000

    # DW 스키마 접두사
    DW_SCHEMA: str = "dw"

    # 외부 서비스 URL — 환경별로 오버라이드 가능
    SYNAPSE_BASE_URL: str = "http://synapse-svc:8003"
    VISION_BASE_URL: str = "http://vision-svc:8000"
    WEAVER_BASE_URL: str = "http://weaver-svc:8001"

    model_config = ConfigDict(env_file=".env")


settings = Settings()
