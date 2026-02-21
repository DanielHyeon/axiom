# Axiom Core - 환경 설정 및 시크릿 관리

## 이 문서가 답하는 질문

- 어떤 환경 변수가 필요하고, 각각의 의미는 무엇인가?
- 시크릿은 어떻게 안전하게 관리하는가?
- 환경별로 어떤 설정이 달라지는가?

<!-- affects: operations -->
<!-- requires-update: 08_operations/deployment.md -->

---

## 1. 환경 변수 목록

운영/개발/통합 테스트는 모두 PostgreSQL(`DATABASE_URL`) 기준으로 동작한다.
SQLite 기반 테스트 경로는 유지하지 않는다.

### 1.1 필수 환경 변수

| 변수명 | 설명 | 예시 | 시크릿 |
|--------|------|------|:------:|
| `DATABASE_URL` | PostgreSQL 접속 URL | `postgresql+asyncpg://user:pass@host:5432/axiom` | O |
| `REDIS_URL` | Redis 접속 URL | `redis://host:6379` | O |
| `JWT_SECRET_KEY` | JWT 서명 키 | `<256bit random>` | O |
| `JWT_ALGORITHM` | JWT 알고리즘 | `HS256` 또는 `RS256` | X |
| `OPENAI_API_KEY` | OpenAI API 키 | `sk-...` | O |

### 1.2 선택 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|-------|
| `DEFAULT_LLM_PROVIDER` | 기본 LLM 프로바이더 | `openai` |
| `DEFAULT_LLM_MODEL` | 기본 LLM 모델 | `gpt-4o` |
| `ANTHROPIC_API_KEY` | Anthropic API 키 | (없음) |
| `GOOGLE_API_KEY` | Google Gemini API 키 | (없음) |
| `OLLAMA_BASE_URL` | Ollama 서버 URL | `http://localhost:11434` |
| `MINIO_ENDPOINT` | MinIO/S3 엔드포인트 | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO/S3 접근 키 | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO/S3 시크릿 키 | `minioadmin` |
| `NEO4J_URI` | Neo4j 접속 URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j 사용자 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 비밀번호 | (없음) |
| `CORS_ORIGINS` | CORS 허용 출처 | `http://localhost:3000` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |
| `LANGCHAIN_TRACING_V2` | LangSmith 추적 활성화 | `false` |
| `LANGCHAIN_API_KEY` | LangSmith API 키 | (없음) |
| `WORKER_POLL_INTERVAL` | Sync Worker 폴링 간격 (초) | `5` |
| `RATE_LIMIT_DEFAULT` | 기본 속도 제한 (req/min) | `100` |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Circuit Breaker 실패 임계값 | `5` |
| `CIRCUIT_BREAKER_OPEN_DURATION` | Circuit Breaker OPEN 유지 시간 (초) | `30` |
| `DLQ_MAX_DEPTH` | DLQ 경고 알림 임계값 | `100` |
| `DLQ_RETENTION_DAYS` | DLQ 메시지 보존 기간 (일) | `30` |

---

## 2. Pydantic Settings 구현

```python
# app/core/config.py

from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    """환경 설정 - 모든 설정은 여기에 정의"""

    # DB
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 80

    # Redis
    REDIS_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4o"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "axiom-documents"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # Worker
    WORKER_POLL_INTERVAL: int = 5

    # Rate Limiting
    RATE_LIMIT_DEFAULT: int = 100

    # Circuit Breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_OPEN_DURATION: int = 30

    # DLQ
    DLQ_MAX_DEPTH: int = 100
    DLQ_RETENTION_DAYS: int = 30

    # Monitoring
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()
```

---

## 3. 시크릿 관리

### 3.1 환경별 시크릿 관리 방법

| 환경 | 방법 | 도구 |
|------|------|------|
| 개발 | `.env` 파일 (Git에 커밋하지 않음) | dotenv |
| 스테이징 | AWS Secrets Manager | K8s ExternalSecrets |
| 프로덕션 | AWS Secrets Manager + 자동 로테이션 | K8s ExternalSecrets |

### 3.2 시크릿 관리 규칙

```
[필수] .env 파일은 .gitignore에 등록한다.
[필수] API 키는 환경 변수로만 주입한다 (코드에 하드코딩 금지).
[필수] 시크릿 로테이션은 90일 주기로 수행한다.
[금지] 시크릿을 로그에 출력하지 않는다.
[금지] 시크릿을 에러 메시지에 포함하지 않는다.
[금지] .env 파일을 Docker 이미지에 포함하지 않는다.
```

### 3.3 .env.example

```bash
# .env.example - 개발자가 복사하여 .env로 사용
DATABASE_URL=postgresql+asyncpg://axiom:axiom_dev@localhost:5432/axiom
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=change-this-to-a-random-256bit-key
OPENAI_API_KEY=sk-your-key-here
```

---

## 근거

- K-AIR 역설계 보고서 섹션 12.3 (필수 환경변수)
- K-AIR process-gpt-main (configmap-example.yaml, secrets-example.yaml)
- K-AIR 주의사항: Neo4j 비밀번호 평문 저장 -> Axiom에서 시크릿 관리 강화
- [08_operations/performance-monitoring.md](./performance-monitoring.md) (Connection Pool, Rate Limiting 등 성능 관련 설정 기준값)
- [08_operations/logging-system.md](./logging-system.md) (LOG_LEVEL 동적 변경 API, 로그 포맷 설정, 감사 로그 설정)
