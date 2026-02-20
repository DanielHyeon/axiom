# 서비스 내부 구조

## 이 문서가 답하는 질문

- Oracle 서비스의 디렉터리 구조와 모듈 구성은?
- 각 모듈의 책임과 의존 관계는?
- 코드 리뷰 시 어떤 규칙을 적용해야 하는가?

<!-- affects: 01_architecture -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

---

## 1. 디렉터리 구조

```
services/oracle/
├── docs/                          # 이 문서들
├── app/
│   ├── main.py                    # FastAPI 앱 엔트리포인트
│   ├── config.py                  # 환경 설정 (Pydantic Settings)
│   │
│   ├── routers/                   # API 계층 (HTTP 요청/응답)
│   │   ├── __init__.py
│   │   ├── ask.py                 # POST /text2sql/ask
│   │   ├── react.py               # POST /text2sql/react (NDJSON)
│   │   ├── direct_sql.py          # POST /text2sql/direct-sql
│   │   ├── meta.py                # GET /text2sql/meta/*
│   │   ├── feedback.py            # POST /text2sql/feedback
│   │   ├── history.py             # GET /text2sql/history
│   │   └── events.py              # /text2sql/events/* (Core Watch 이관 예정)
│   │
│   ├── pipelines/                 # 파이프라인 계층 (워크플로우 오케스트레이션)
│   │   ├── __init__.py
│   │   ├── nl2sql_pipeline.py     # Ask 파이프라인 (8단계)
│   │   └── react_pipeline.py      # ReAct 파이프라인 (6단계)
│   │
│   ├── core/                      # 코어 모듈 (비즈니스 로직 단위)
│   │   ├── __init__.py
│   │   ├── graph_search.py        # Synapse Graph API 5축 검색 어댑터 (352줄)
│   │   ├── prompt.py              # LangChain SQL 프롬프트 (112줄)
│   │   ├── sql_exec.py            # SQL 실행 엔진 (380줄)
│   │   ├── sql_guard.py           # SQL 안전성 검증 (153줄)
│   │   ├── llm_factory.py         # LLM 팩토리 (213줄)
│   │   ├── embedding.py           # 텍스트 벡터화 (55줄)
│   │   ├── viz.py                 # 시각화 추천 (297줄)
│   │   ├── cache_postprocess.py   # 캐시 후처리 (1977줄)
│   │   └── enum_cache_bootstrap.py # Enum 캐싱 (513줄)
│   │
│   ├── models/                    # 데이터 모델 (Pydantic / SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── request.py             # API 요청 모델
│   │   ├── response.py            # API 응답 모델
│   │   ├── history.py             # 쿼리 이력 모델
│   │   ├── schema.py              # 스키마 검색 결과 모델
│   │   └── event.py               # 이벤트 룰 모델
│   │
│   ├── repositories/              # 데이터 접근 계층
│   │   ├── __init__.py
│   │   ├── synapse_repo.py        # Synapse Graph/Meta API 접근
│   │   ├── history_repo.py        # 쿼리 이력 접근
│   │   └── event_repo.py          # 이벤트 룰 접근
│   │
│   └── utils/                     # 유틸리티
│       ├── __init__.py
│       ├── logger.py              # 구조화 로깅
│       └── metrics.py             # 메트릭 수집
│
├── tests/                         # 테스트
│   ├── unit/
│   │   ├── test_sql_guard.py
│   │   ├── test_graph_search.py
│   │   └── test_embedding.py
│   ├── integration/
│   │   ├── test_nl2sql_pipeline.py
│   │   └── test_synapse_connection.py
│   └── conftest.py
│
├── pyproject.toml                 # 프로젝트 설정
├── Dockerfile                     # 컨테이너 빌드
└── docker-compose.yml             # 로컬 개발 환경
```

---

## 2. 계층 간 의존 규칙

```
┌─────────────────┐
│   routers/      │  → HTTP만 처리. 비즈니스 로직 없음
│   (API 계층)    │
└────────┬────────┘
         │ 호출
         ▼
┌─────────────────┐
│   pipelines/    │  → 코어 모듈을 조합. LLM/DB 직접 호출 없음
│   (파이프라인)  │
└────────┬────────┘
         │ 호출
         ▼
┌─────────────────┐
│   core/         │  → 독립적 비즈니스 로직. 서로 간 순환 의존 없음
│   (코어 모듈)   │
└────────┬────────┘
         │ 호출
         ▼
┌─────────────────┐
│  repositories/  │  → 데이터 접근만. 비즈니스 로직 없음
│  models/        │
│  (데이터 계층)  │
└─────────────────┘
```

### 2.1 허용되는 의존 방향

| 호출자 | 피호출 가능 대상 |
|--------|-----------------|
| `routers/` | `pipelines/`, `models/` |
| `pipelines/` | `core/`, `models/` |
| `core/` | `repositories/`, `models/`, `utils/` |
| `repositories/` | `models/`, `utils/` |

### 2.2 금지되는 의존

| 금지 | 이유 |
|------|------|
| `routers/` -> `core/` | 파이프라인을 거쳐야 함 |
| `routers/` -> `repositories/` | 데이터 접근은 코어를 통해야 함 |
| `core/` -> `core/` (순환) | 순환 의존은 테스트 불가 |
| `core/` -> `pipelines/` | 역방향 의존 |
| `repositories/` -> `core/` | 역방향 의존 |

---

## 3. 모듈별 책임

### 3.1 routers/ (API 계층)

| 파일 | 책임 | 코드 리뷰 체크 |
|------|------|---------------|
| `ask.py` | NL2SQL 요청 수신, 응답 포맷팅 | 비즈니스 로직 없는지 확인 |
| `react.py` | ReAct 스트리밍 응답 관리 | NDJSON 형식 준수 여부 |
| `direct_sql.py` | 직접 SQL 수신, 권한 검증 | Admin 권한 체크 존재 여부 |
| `meta.py` | 메타데이터 조회, 페이지네이션 | 페이지네이션 로직 정확성 |
| `feedback.py` | 피드백 수신, 유효성 검증 | 입력 검증 로직 |
| `history.py` | 이력 조회, 필터링 | 사용자별 접근 제어 |
| `events.py` | 이벤트 CRUD, 스케줄러 제어 | Core Watch 이관 호환성 |

### 3.2 pipelines/ (파이프라인 계층)

| 파일 | 책임 | 코드 리뷰 체크 |
|------|------|---------------|
| `nl2sql_pipeline.py` | 8단계 파이프라인 오케스트레이션 | 각 단계 에러 처리, 타임아웃 |
| `react_pipeline.py` | ReAct 6단계 루프 관리 | 최대 반복 횟수 제어, 스트리밍 |

### 3.3 core/ (코어 모듈)

| 파일 | 책임 | K-AIR 원본 줄 수 | 코드 리뷰 체크 |
|------|------|:---------:|---------------|
| `graph_search.py` | 5축 벡터 검색 + FK 탐색 | 352 | 벡터 유사도 임계값, FK 홉 제한 |
| `prompt.py` | SQL 생성 프롬프트 관리 | 112 | 프롬프트 인젝션 방어 |
| `sql_exec.py` | 비동기 SQL 실행 | 380 | 타임아웃, 커넥션 풀, 에러 처리 |
| `sql_guard.py` | SQL 안전성 4계층 검증 | 153 | 블랙리스트 완전성, SQLGlot 파싱 |
| `llm_factory.py` | LLM 프로바이더 추상화 | 213 | 프로바이더 폴백, 에러 처리 |
| `embedding.py` | 텍스트 벡터화 | 55 | 모델 일관성, 차원 검증 |
| `viz.py` | 시각화 추천 알고리즘 | 297 | 추천 규칙 정확성 |
| `cache_postprocess.py` | 품질 게이트 + 영속화 | 1,977 | 백그라운드 에러 처리, 메모리 누수 |
| `enum_cache_bootstrap.py` | Enum 값 캐싱 | 513 | 시작 시 성능 영향, 캐시 무효화 |

---

## 4. 설정 관리

### 4.1 config.py 구조

```python
from pydantic_settings import BaseSettings

class OracleSettings(BaseSettings):
    """Oracle 서비스 설정. 환경 변수로 오버라이드 가능."""

    # Synapse (Graph/Meta API)
    synapse_base_url: str = "http://localhost:8003/api/v1"
    synapse_service_token: str  # required, no default

    # Target DB
    target_db_type: str = "postgresql"  # postgresql | mysql
    target_db_url: str  # required, no default

    # LLM
    llm_provider: str = "openai"  # openai | google | compatible
    llm_model: str = "gpt-4o"
    llm_api_key: str  # required, no default
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

    # Pipeline
    sql_timeout: int = 30
    max_rows: int = 10000
    row_limit: int = 1000
    max_join_depth: int = 5
    max_subquery_depth: int = 3
    vector_top_k: int = 10
    max_fk_hops: int = 3

    # Quality Gate
    judge_rounds: int = 2
    conf_threshold: float = 0.90

    class Config:
        env_prefix = "ORACLE_"
        env_file = ".env"
```

### 4.2 환경 변수 매핑

| 환경 변수 | 설정 키 | 필수 |
|-----------|---------|------|
| `ORACLE_SYNAPSE_BASE_URL` | `synapse_base_url` | No (기본값 있음) |
| `ORACLE_SYNAPSE_SERVICE_TOKEN` | `synapse_service_token` | Yes |
| `ORACLE_TARGET_DB_URL` | `target_db_url` | Yes |
| `ORACLE_LLM_API_KEY` | `llm_api_key` | Yes |
| `ORACLE_SQL_TIMEOUT` | `sql_timeout` | No (기본: 30) |

---

## 5. 에러 처리 전략

### 5.1 계층별 에러 처리

| 계층 | 에러 처리 방식 |
|------|-------------|
| `routers/` | HTTPException 반환, 구조화된 에러 응답 |
| `pipelines/` | 도메인 예외 발생 (NL2SQLError, GuardError 등) |
| `core/` | 구체적 예외 발생 또는 Result 패턴 반환 |
| `repositories/` | DB 관련 예외를 도메인 예외로 래핑 |

### 5.2 예외 계층

```python
class OracleError(Exception):
    """Oracle 모듈 기본 예외"""
    pass

class SchemaNotFoundError(OracleError):
    """관련 스키마를 찾지 못함"""
    pass

class SQLGuardRejectError(OracleError):
    """SQL Guard에 의해 거부됨"""
    def __init__(self, violations: list[str]):
        self.violations = violations

class SQLExecutionError(OracleError):
    """SQL 실행 에러"""
    pass

class SQLTimeoutError(SQLExecutionError):
    """SQL 실행 타임아웃"""
    pass

class LLMUnavailableError(OracleError):
    """LLM 서비스 불가"""
    pass
```

---

## 6. 코드 리뷰 기준

이 문서는 코드 리뷰의 기준이 된다.

### 6.1 필수 체크리스트

- [ ] 계층 간 의존 규칙 준수 여부
- [ ] 새로운 라우터에 파이프라인 위임 여부
- [ ] 코어 모듈의 독립 테스트 가능 여부
- [ ] SQL Guard를 우회하는 경로 없는지 확인
- [ ] 비동기 I/O 사용 (동기 DB 드라이버 사용 금지)
- [ ] 환경 변수로 설정 오버라이드 가능 여부
- [ ] 에러 처리에서 스택 트레이스가 사용자에게 노출되지 않는지

### 6.2 경고 체크리스트

- [ ] `cache_postprocess.py` 수정 시 메모리 누수 점검
- [ ] `graph_search.py` 수정 시 검색 성능 영향 평가
- [ ] `prompt.py` 수정 시 프롬프트 인젝션 가능성 평가
- [ ] `events.py` 수정 시 Core Watch 이관 호환성 유지

---

## 관련 문서

- [01_architecture/architecture-overview.md](../01_architecture/architecture-overview.md): 아키텍처 개요
- [08_operations/deployment.md](../08_operations/deployment.md): 배포 절차
