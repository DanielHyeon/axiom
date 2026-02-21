# Weaver 서비스 내부 구조

<!-- affects: backend -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

## 이 문서가 답하는 질문

- Weaver 백엔드의 디렉토리 구조는 어떻게 되는가?
- 각 모듈의 책임은 무엇인가?
- 의존성 주입과 설정 관리는 어떻게 하는가?
- 코드 리뷰 기준은 무엇인가?

---

## 1. 디렉토리 구조

```
services/weaver/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 앱 초기화, 라우터 등록
│   ├── config.py                  # 환경 설정 (Pydantic Settings)
│   │
│   ├── api/                       # API 라우터 (Controller 계층)
│   │   ├── __init__.py
│   │   ├── datasources.py        # 데이터소스 CRUD 엔드포인트
│   │   ├── query.py              # SQL 쿼리 실행 엔드포인트
│   │   └── metadata.py           # 메타데이터 추출 엔드포인트 (SSE)
│   │
│   ├── schemas/                   # Pydantic 모델 (Request/Response)
│   │   ├── __init__.py
│   │   ├── datasource.py         # DataSourceCreate, DataSourceResponse 등
│   │   ├── query.py              # QueryRequest, QueryResponse 등
│   │   └── metadata.py           # MetadataRequest, ProgressEvent 등
│   │
│   ├── services/                  # 비즈니스 로직 (Service 계층)
│   │   ├── __init__.py
│   │   ├── datasource_service.py # 데이터소스 관리 로직
│   │   ├── query_service.py      # 쿼리 실행 로직
│   │   └── introspection_service.py # 메타데이터 추출 오케스트레이션
│   │
│   ├── adapters/                  # DB 엔진별 어댑터 (Adapter 계층)
│   │   ├── __init__.py
│   │   ├── base.py               # BaseAdapter 추상 클래스
│   │   ├── postgresql.py         # PostgreSQL 어댑터
│   │   ├── mysql.py              # MySQL 어댑터
│   │   ├── oracle.py             # Oracle 어댑터
│   │   └── factory.py            # AdapterFactory
│   │
│   ├── mindsdb/                   # MindsDB 클라이언트 (Infrastructure 계층)
│   │   ├── __init__.py
│   │   └── client.py             # MindsDB HTTP API 클라이언트
│   │
│   ├── neo4j/                     # Neo4j 서비스 (Infrastructure 계층)
│   │   ├── __init__.py
│   │   ├── client.py             # Neo4j 드라이버 관리
│   │   └── metadata_store.py     # 메타데이터 CRUD
│   │
│   └── core/                      # 공통 유틸리티
│       ├── __init__.py
│       ├── errors.py             # 표준 에러 정의
│       ├── logging.py            # 로깅 설정
│       └── security.py           # 비밀번호 암호화 등
│
├── tests/
│   ├── unit/
│   │   ├── test_adapters/
│   │   ├── test_services/
│   │   └── test_mindsdb/
│   ├── integration/
│   │   ├── test_datasource_api.py
│   │   ├── test_query_api.py
│   │   └── test_metadata_api.py
│   └── conftest.py
│
├── docs/                          # 이 문서들
├── pyproject.toml                 # 의존성 및 빌드 설정
└── Dockerfile
```

---

## 2. 계층 구조와 의존성 규칙

```
┌─ API Layer ─────────────────────────────────────┐
│  api/datasources.py, api/query.py, api/metadata.py │
│  책임: HTTP 요청 수신, 입력 검증, 응답 반환         │
└────────────────────┬────────────────────────────────┘
                     │ 호출
                     ▼
┌─ Service Layer ────────────────────────────────────┐
│  services/datasource_service.py                     │
│  services/query_service.py                          │
│  services/introspection_service.py                  │
│  책임: 비즈니스 로직 조합, 트랜잭션 경계             │
└────────┬──────────────┬────────────────┬────────────┘
         │              │                │ 호출
         ▼              ▼                ▼
┌─ Infrastructure Layer ────────────────────────────────┐
│  mindsdb/client.py    neo4j/metadata_store.py         │
│  adapters/postgresql.py, mysql.py, oracle.py          │
│  책임: 외부 시스템 통신                                │
└───────────────────────────────────────────────────────┘
```

### 의존성 규칙

| 규칙 | 설명 |
|------|------|
| **상위 → 하위만 호출** | API → Service → Infrastructure. 역방향 호출 금지 |
| **같은 계층 호출 금지** | Service가 다른 Service를 직접 호출하지 않음 |
| **Infrastructure 간 독립** | MindsDB 클라이언트가 Neo4j에 접근하지 않음 |
| **Schemas 공유** | Pydantic 모델은 모든 계층에서 참조 가능 |

### 금지사항

```
금지:
  - api/datasources.py에서 neo4j/client.py를 직접 import
  - adapters/postgresql.py에서 neo4j/metadata_store.py를 import
  - services/query_service.py에서 services/datasource_service.py를 import
  - MindsDB 클라이언트에서 비즈니스 로직 포함

필수:
  - 모든 외부 통신은 Infrastructure 계층에서만
  - 모든 입력 검증은 Pydantic 모델에서
  - 모든 에러 변환은 Service 계층에서
```

---

## 3. FastAPI 앱 초기화

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import datasources, query, metadata
from app.mindsdb.client import MindsDBClient
from app.neo4j.client import Neo4jClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    app.state.mindsdb = MindsDBClient(
        base_url=settings.MINDSDB_URL,
        timeout=settings.MINDSDB_TIMEOUT,
    )
    app.state.neo4j = Neo4jClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )
    await app.state.neo4j.verify_connectivity()

    yield

    # Shutdown
    await app.state.neo4j.close()


app = FastAPI(
    title="Axiom Weaver",
    description="Data Fabric Service - Multi-DB Abstraction & Metadata Management",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - production uses specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # NOT ["*"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router registration
app.include_router(datasources.router, prefix="/api/datasources", tags=["datasources"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(metadata.router, prefix="/api/metadata", tags=["metadata"])
```

---

## 4. 설정 관리

```python
# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Environment configuration

    All sensitive values come from environment variables.
    .env file is supported for local development only.
    """

    # Application
    APP_NAME: str = "axiom-weaver"
    APP_ENV: str = "development"  # development | staging | production
    LOG_LEVEL: str = "INFO"

    # MindsDB
    MINDSDB_URL: str = "http://localhost:47334"
    MINDSDB_TIMEOUT: int = 120  # seconds

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str  # Required, no default

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Security
    ENCRYPTION_KEY: str  # Required, for password encryption

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
```

---

## 5. 에러 처리 표준

```python
# app/core/errors.py
from fastapi import HTTPException


class WeaverError(Exception):
    """Base Weaver error"""
    def __init__(self, code: str, message: str, status_code: int = 500, details: dict = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class DataSourceNotFoundError(WeaverError):
    def __init__(self, name: str):
        super().__init__(
            code="NOT_FOUND",
            message=f"DataSource '{name}' not found",
            status_code=404,
        )


class DuplicateDataSourceError(WeaverError):
    def __init__(self, name: str):
        super().__init__(
            code="DUPLICATE_NAME",
            message=f"DataSource with name '{name}' already exists",
            status_code=409,
        )


class MindsDBUnavailableError(WeaverError):
    def __init__(self):
        super().__init__(
            code="MINDSDB_UNAVAILABLE",
            message="MindsDB server is not available",
            status_code=503,
        )


class UnsupportedEngineError(WeaverError):
    def __init__(self, engine: str):
        super().__init__(
            code="UNSUPPORTED_ENGINE",
            message=f"Engine '{engine}' does not support metadata extraction",
            status_code=400,
        )


class QueryTimeoutError(WeaverError):
    def __init__(self, timeout: int):
        super().__init__(
            code="QUERY_TIMEOUT",
            message=f"Query execution timed out after {timeout} seconds",
            status_code=408,
        )
```

### 글로벌 에러 핸들러

```python
# app/main.py (추가)
from app.core.errors import WeaverError


@app.exception_handler(WeaverError)
async def weaver_error_handler(request, exc: WeaverError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )
```

---

## 6. 코드 리뷰 기준

이 문서의 구조와 규칙은 **코드 리뷰 기준**이 된다.

| 항목 | 체크 |
|------|------|
| API 라우터에서 비즈니스 로직이 없는가? | 입력 검증과 서비스 호출만 |
| Service에서 직접 HTTP/DB 호출을 하지 않는가? | Infrastructure 계층만 |
| Pydantic 모델로 입력/출력이 정의되어 있는가? | 타입 안전성 |
| 에러가 WeaverError 계층으로 처리되는가? | 표준 에러 형식 |
| Circuit Breaker open 상태가 도메인 예외로 변환되는가? | `MindsDBUnavailableError`, `PostgresStoreUnavailableError`로 일관 처리 |
| 비밀번호가 로그에 노출되지 않는가? | 보안 |
| 새로운 어댑터가 BaseAdapter를 구현하는가? | 인터페이스 준수 |

### 장애 주입 회귀 테스트

- `tests/unit/test_resilience.py`
- 검증 항목:
  - `with_retry` 재시도/최종 예외 전파
  - `SimpleCircuitBreaker` open/timeout reset 경계
  - `MindsDBClient` transient 오류 회복
  - 연속 실패 시 breaker open + fail-fast 동작

---

## 7. 관련 문서

| 문서 | 설명 |
|------|------|
| `03_backend/mindsdb-client.md` | MindsDB 클라이언트 상세 |
| `03_backend/schema-introspection.md` | 인트로스펙션 서비스 상세 |
| `03_backend/neo4j-metadata.md` | Neo4j 메타데이터 관리 |
| `08_operations/deployment.md` | 배포 및 환경 설정 |
| `03_backend/metadata-propagation.md` | 메타데이터 변경 전파 메커니즘 |
