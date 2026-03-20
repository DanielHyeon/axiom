# 서비스 내부 구조

> 상태: 구현 완료 기준 문서 (2026-03-21 갱신). 실제 코드와 정합성 검증 완료.

## 이 문서가 답하는 질문

- Oracle 서비스의 디렉터리 구조와 모듈 구성은?
- 각 모듈의 책임과 의존 관계는?
- 코드 리뷰 시 어떤 규칙을 적용해야 하는가?

<!-- affects: 01_architecture -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

---

## 1. 디렉터리 구조 (현재 구현 기준)

> 아래는 실제 코드 파일 기준이다 (2026-03-21 검증). api/pipelines/core/infrastructure 구조를 사용한다.

```
services/oracle/
├── docs/                          # 이 문서들
├── app/
│   ├── main.py                    # FastAPI 앱 엔트리포인트 (Lifespan + 데모 시드 데이터)
│   │
│   ├── api/                       # API 계층 (HTTP 요청/응답)
│   │   ├── text2sql.py            # POST /text2sql/ask, /react, /direct-sql, /history
│   │   ├── feedback.py            # POST /feedback, GET /feedback/list
│   │   ├── feedback_stats.py      # GET /feedback/stats/* (summary/trend/failures/by-datasource/top-failed)
│   │   ├── meta.py                # 메타데이터 탐색 (tables/columns/datasources/description 수정)
│   │   ├── events.py              # /text2sql/events/* (Core Watch 프록시) + /text2sql/watch-agent/chat
│   │   └── health.py              # /health, /health/ready 프로브
│   │
│   ├── pipelines/                 # 파이프라인 계층 (워크플로우 오케스트레이션)
│   │   ├── nl2sql_pipeline.py     # Ask 파이프라인 (10단계)
│   │   ├── react_agent.py         # ReAct 파이프라인 (6단계, HIL 지원)
│   │   ├── cache_postprocess.py   # 품질 게이트 + 캐시 저장 + Value Mapping 학습
│   │   └── enum_cache_bootstrap.py # Enum 캐시 부트스트랩 (서비스 시작 시)
│   │
│   ├── core/                      # 코어 모듈 (비즈니스 로직 단위)
│   │   ├── config.py              # 환경 설정 (Pydantic Settings)
│   │   ├── auth.py                # JWT 검증 (Core 동일 비밀키)
│   │   ├── graph_search.py        # RRF 기반 검색 + PRF (현재 모의 데이터)
│   │   ├── schema_context.py      # 서브스키마 컨텍스트 (DDL 축소)
│   │   ├── sql_exec.py            # SQL 실행 (4모드: direct_pg/weaver/hybrid/mock)
│   │   ├── sql_guard.py           # SQLGlot AST 기반 SQL 안전성 검증
│   │   ├── llm_factory.py         # LLM 팩토리 (MockLLM 스마트 모드)
│   │   ├── quality_judge.py       # LLM 기반 N-라운드 품질 심사기
│   │   ├── value_mapping.py       # 자연어 -> DB 값 매핑 3단계 파이프라인
│   │   ├── visualize.py           # 시각화 추천 (컬럼 역할 추론 기반)
│   │   ├── query_history.py       # PostgreSQL 쿼리 이력 저장소 (인메모리 폴백)
│   │   ├── feedback_analytics.py  # asyncpg 기반 피드백 통계 집계
│   │   ├── synapse_client.py      # Synapse API 클라이언트
│   │   ├── rate_limit.py          # 인메모리 Rate Limiter
│   │   └── security.py            # 역할별 행 제한 + PII 마스킹
│   │
│   ├── infrastructure/            # 외부 시스템 연동 (Anti-Corruption Layer)
│   │   └── acl/
│   │       ├── synapse_acl.py     # Anti-Corruption Layer: Synapse BC
│   │       └── weaver_acl.py      # Anti-Corruption Layer: Weaver BC
│   │
│   └── prompts/                   # LLM 프롬프트 템플릿
│       └── quality_gate_prompt.md # 품질 게이트 시스템 프롬프트
│
├── pyproject.toml                 # 프로젝트 설정
├── Dockerfile                     # 컨테이너 빌드
└── docker-compose.yml             # 로컬 개발 환경
```

---

## 2. 계층 간 의존 규칙

```
┌─────────────────┐
│   api/          │  → HTTP만 처리. 비즈니스 로직 없음
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
┌──────────────────┐
│  infrastructure/ │  → 외부 시스템 연동 (ACL). 비즈니스 로직 없음
│  (데이터 계층)   │
└──────────────────┘
```

### 2.1 허용되는 의존 방향

| 호출자 | 피호출 가능 대상 |
|--------|-----------------|
| `api/` | `pipelines/`, `core/` (인증/설정만) |
| `pipelines/` | `core/`, `infrastructure/` |
| `core/` | `infrastructure/`, `core/config.py` |
| `infrastructure/` | (외부 시스템만) |

### 2.2 금지되는 의존

| 금지 | 이유 |
|------|------|
| `api/` -> `infrastructure/` 직접 | ACL은 파이프라인/코어를 거쳐야 함 |
| `core/` -> `core/` (순환) | 순환 의존은 테스트 불가 |
| `core/` -> `pipelines/` | 역방향 의존 |
| `infrastructure/` -> `core/` | 역방향 의존 |

---

## 3. 모듈별 책임

### 3.1 api/ (API 계층)

| 파일 | 책임 | 코드 리뷰 체크 |
|------|------|---------------|
| `text2sql.py` | /ask, /react, /direct-sql, /history 엔드포인트 | 비즈니스 로직 없는지, NDJSON 형식 준수 여부 |
| `feedback.py` | 피드백 제출 + 목록 조회 | 입력 검증 로직 |
| `feedback_stats.py` | 피드백 통계 대시보드 (summary/trend/failures/by-datasource/top-failed) | admin/manager 역할 체크 |
| `meta.py` | 메타데이터 탐색 (tables/columns/datasources/description 수정) | 페이지네이션 로직 정확성 |
| `events.py` | /text2sql/events/* (Core Watch 프록시) + /text2sql/watch-agent/chat | Core Watch 프록시 정합성 |
| `health.py` | /health, /health/ready 프로브 | 의존 서비스 체크 |

### 3.2 pipelines/ (파이프라인 계층)

| 파일 | 책임 | 코드 리뷰 체크 |
|------|------|---------------|
| `nl2sql_pipeline.py` | 10단계 Ask 파이프라인 오케스트레이션 | 각 단계 에러 처리, 타임아웃 |
| `react_agent.py` | ReAct 6단계 루프 관리 (HIL 지원) | 최대 반복 횟수 제어, 스트리밍 |
| `cache_postprocess.py` | 품질 게이트 + 캐시 저장 + Value Mapping 학습 | 백그라운드 에러 처리, 메모리 누수 |
| `enum_cache_bootstrap.py` | Enum 캐시 부트스트랩 (서비스 시작 시) | 시작 시 성능 영향, 캐시 무효화 |

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
from pydantic import ConfigDict

class Settings(BaseSettings):
    """Oracle 서비스 설정. 환경 변수로 오버라이드 가능."""

    ENVIRONMENT: str = "development"
    JWT_SECRET_KEY: str = "axiom-dev-secret-key-do-not-use-in-production"
    JWT_ALGORITHM: str = "HS256"
    SYNAPSE_API_URL: str = "http://localhost:8003"
    CORE_API_URL: str = "http://localhost:8001"
    SERVICE_TOKEN_ORACLE: str = "local-oracle-token"
    WEAVER_QUERY_API_URL: str = "http://localhost:8001/api/query"
    WEAVER_BEARER_TOKEN: str = ""
    ORACLE_SQL_EXECUTION_MODE: str = "hybrid"  # mock | hybrid | weaver | direct
    ORACLE_SQL_EXECUTION_TIMEOUT_SEC: int = 15
    ORACLE_DATASOURCES_JSON: str = "[]"
    QUERY_HISTORY_DATABASE_URL: str = "postgresql://arkos:arkos@localhost:5432/insolvency_os"
    WEAVER_INSIGHT_URL: str = "http://weaver:8001/api/insight/logs"
    WEAVER_INSIGHT_TOKEN: str = ""

    # Feature Flags
    ENABLE_QUALITY_GATE: bool = True
    ENABLE_VALUE_MAPPING: bool = True

    # Enum Cache Bootstrap
    ENUM_CACHE_ENABLED: bool = True
    ENUM_CACHE_MAX_VALUES: int = 100
    ENUM_CACHE_MAX_COLUMNS: int = 2000
    ENUM_CACHE_TARGET_SCHEMA: str = "public"

    model_config = ConfigDict(env_file=".env")

settings = Settings()
```

> **참고**: `env_prefix`를 사용하지 않는다. 환경변수명을 설정 키와 동일하게 직접 지정한다.

### 4.2 주요 환경 변수

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `ORACLE_SQL_EXECUTION_MODE` | `hybrid` | SQL 실행 모드 (mock/hybrid/weaver/direct) |
| `ORACLE_SQL_EXECUTION_TIMEOUT_SEC` | `15` | SQL 실행 타임아웃 (초) |
| `QUERY_HISTORY_DATABASE_URL` | (로컬 PG) | 쿼리 이력 PostgreSQL URL |
| `ENABLE_QUALITY_GATE` | `True` | 품질 게이트 활성화 여부 |
| `ENABLE_VALUE_MAPPING` | `True` | Value Mapping 활성화 여부 |

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
