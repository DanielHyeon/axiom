# Vision 서비스 내부 구조

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **근거**: 01_architecture/architecture-overview.md

---

## 이 문서가 답하는 질문

- Vision 서비스의 내부 레이어 구조와 의존성 규칙은?
- 트랜잭션 경계는 어디인가?
- DB 접근 규칙은 무엇인가?
- 동시성 정책은 어떻게 되는가?
- 이 문서는 코드 리뷰 기준이 된다

---

## 1. 4레이어 아키텍처

```
┌─ API 레이어 (app/api/) ────────────────────────────────────────┐
│  역할: HTTP 프로토콜 관심사만 처리                               │
│  - FastAPI Router 정의                                          │
│  - Request/Response 직렬화/역직렬화 (Pydantic)                  │
│  - HTTP 상태 코드 결정                                          │
│  - 인증/인가 검증 (Depends)                                     │
│  - Background task 디스패치                                     │
│                                                                  │
│  금지: SQL 직접 실행, 비즈니스 로직 포함                         │
│  허용: 엔진 레이어 호출, 스키마 변환                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ 엔진 레이어 (app/engines/) ──────────────────────────────┐ │
│  │  역할: 핵심 비즈니스/계산 로직                              │ │
│  │  - 시나리오 솔버 (scipy)                                    │ │
│  │  - Mondrian XML 파서                                        │ │
│  │  - 피벗 SQL 생성기                                          │ │
│  │  - ETL 서비스                                               │ │
│  │  - 인과 추론 엔진 (DoWhy)                                   │ │
│  │  - NL→피벗 워크플로우 (LangGraph)                           │ │
│  │                                                              │ │
│  │  금지: HTTP 관심사, FastAPI 의존성                           │ │
│  │  허용: 모델 레이어 접근, 외부 서비스 호출                   │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  모델 레이어 (app/models/)                                      │
│  역할: SQLAlchemy ORM 모델, 테이블 매핑                         │
│  - Scenario, ScenarioResult, CubeMetadata 등                    │
│  - Materialized View 매핑 (read-only)                           │
│                                                                  │
│  금지: 비즈니스 로직, HTTP 관심사                                │
├──────────────────────────────────────────────────────────────────┤
│  코어 레이어 (app/core/)                                        │
│  역할: 횡단 관심사                                               │
│  - config.py: Pydantic Settings (환경 변수)                     │
│  - database.py: AsyncSession factory                            │
│  - dependencies.py: FastAPI Depends 공통                        │
│  - exceptions.py: 도메인 예외 정의                              │
└──────────────────────────────────────────────────────────────────┘
```

### 1.1 의존성 규칙 (Import 방향)

```
api/ → engines/ → models/
  ↘      ↓          ↓
   core/ ←──────────┘

허용: api → engines, api → core, engines → models, engines → core
금지: engines → api, models → engines, models → api
금지: engines 간 직접 import (scenario_solver ↛ pivot_engine)
```

---

## 2. 트랜잭션 경계

### 2.1 트랜잭션 규칙

| 작업 | 트랜잭션 범위 | 격리 수준 |
|------|-------------|----------|
| 시나리오 CRUD | 단일 트랜잭션 | READ COMMITTED |
| 시나리오 계산 (compute) | 분리된 트랜잭션 (결과 저장만) | READ COMMITTED |
| 피벗 쿼리 | READ-ONLY 트랜잭션 | REPEATABLE READ |
| ETL Sync | 자체 트랜잭션 (MV REFRESH) | - |
| 인과 분석 | 분리된 트랜잭션 (결과 저장만) | READ COMMITTED |

### 2.2 트랜잭션 패턴

```python
# Pattern 1: Simple CRUD (single transaction)
@router.post("/what-if")
async def create_scenario(
    request: ScenarioCreate,
    db: AsyncSession = Depends(get_db)
):
    async with db.begin():
        scenario = Scenario(**request.model_dump())
        db.add(scenario)
        # Transaction commits on context exit
    return scenario

# Pattern 2: Async compute (separate transaction for result save)
async def run_scenario_solver(scenario_id: UUID):
    # Read scenario (transaction 1)
    async with get_session() as db:
        scenario = await db.get(Scenario, scenario_id)

    # CPU-intensive computation (no transaction)
    result = await compute_in_thread(scenario)

    # Save result (transaction 2)
    async with get_session() as db:
        async with db.begin():
            await db.execute(
                update(Scenario)
                .where(Scenario.id == scenario_id)
                .values(status=ScenarioStatus.COMPLETED)
            )
            db.add(ScenarioResult(**result))

# Pattern 3: Read-only query (pivot)
@router.post("/pivot/query")
async def execute_pivot(
    request: PivotRequest,
    db: AsyncSession = Depends(get_db)
):
    async with db.begin():
        # Set read-only hint
        await db.execute(text("SET TRANSACTION READ ONLY"))
        result = await db.execute(text(generated_sql))
        return result.fetchall()
```

---

## 3. DB 접근 규칙

### 3.1 허용/금지 테이블

| 테이블/뷰 | 읽기 | 쓰기 | 비고 |
|-----------|:----:|:----:|------|
| `what_if_scenarios` | O | O | Vision 소유 |
| `scenario_parameter_overrides` | O | O | Vision 소유 |
| `scenario_results` | O | O | Vision 소유 |
| `mv_business_fact` (MV) | O | X | REFRESH만 허용 |
| `mv_cashflow_fact` (MV) | O | X | REFRESH만 허용 |
| `dim_*` 디멘전 테이블 | O | X | REFRESH만 허용 |
| `causal_graphs` | O | O | Vision 소유 [Phase 4] |
| `case_causal_analysis` | O | O | Vision 소유 [Phase 4] |
| `causal_explanations` | O | O | Vision 소유 [Phase 4] |
| `cases` (Core 소유) | O | X | 읽기만 허용 |
| `records` (Core 소유) | O | X | 읽기만 허용 |
| `assets` (Core 소유) | O | X | 읽기만 허용 |
| `stakeholders` (Core 소유) | O | X | 읽기만 허용 |

### 3.2 Connection Pool 설정

```python
# database.py
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,          # 기본 연결 수
    max_overflow=10,       # 최대 추가 연결
    pool_timeout=30,       # 연결 대기 타임아웃
    pool_recycle=3600,     # 1시간마다 연결 재생성
    pool_pre_ping=True,    # 연결 유효성 사전 체크
)
```

---

## 4. 동시성 정책

### 4.1 동시 작업 제한

| 작업 | 최대 동시 수 | 구현 |
|------|:----------:|------|
| 시나리오 계산 | 케이스당 3개 | DB 상태 확인 + asyncio.Semaphore |
| OLAP 피벗 쿼리 | 10 (전역) | asyncio.Semaphore |
| NL→피벗 LLM 호출 | 5 (전역) | asyncio.Semaphore |
| ETL Sync | 1 (전역, 뷰 단위) | DB 락 (advisory lock) |
| 인과 분석 | 케이스당 1개 | DB 상태 확인 |

### 4.2 Semaphore 패턴

```python
# Global semaphores
_pivot_semaphore = asyncio.Semaphore(10)
_llm_semaphore = asyncio.Semaphore(5)
_solver_semaphore = asyncio.Semaphore(3)

async def execute_pivot_with_limit(sql: str, db: AsyncSession):
    async with _pivot_semaphore:
        return await asyncio.wait_for(
            db.execute(text(sql)),
            timeout=settings.QUERY_TIMEOUT
        )
```

---

## 5. 에러 처리 전략

### 5.1 예외 계층

```python
# app/core/exceptions.py

class VisionError(Exception):
    """Base exception for Vision module"""
    pass

class SolverError(VisionError):
    """Scenario solver errors"""
    pass

class SolverTimeoutError(SolverError):
    status_code = 504
    detail = "Solver computation timed out"

class SolverInfeasibleError(SolverError):
    status_code = 422
    detail = "No feasible solution found with given constraints"

class OLAPError(VisionError):
    """OLAP engine errors"""
    pass

class SQLValidationError(OLAPError):
    status_code = 422
    detail = "Generated SQL failed validation"

class QueryTimeoutError(OLAPError):
    status_code = 504
    detail = "Query execution timed out"

class CausalError(VisionError):
    """Causal analysis errors"""
    pass

class InsufficientDataError(CausalError):
    status_code = 400
    detail = "Insufficient data for causal analysis"
```

### 5.2 글로벌 예외 핸들러

```python
# app/main.py
@app.exception_handler(VisionError)
async def vision_error_handler(request: Request, exc: VisionError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": type(exc).__name__,
                "message": exc.detail,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )
```

---

## 6. 로깅 정책

```python
# Structured logging with structlog
import structlog

logger = structlog.get_logger()

# Required log fields
logger.info(
    "scenario_compute_started",
    case_id=str(case_id),
    scenario_id=str(scenario_id),
    solver_method="SLSQP",
    constraint_count=len(constraints),
)

# Performance logging (all DB queries)
logger.info(
    "pivot_query_executed",
    cube_name=cube_name,
    execution_time_ms=elapsed_ms,
    row_count=row_count,
    cache_hit=cache_hit,
)
```

---

## 7. 테스트 전략

| 테스트 유형 | 대상 | 도구 |
|-----------|------|------|
| 단위 테스트 | 엔진 레이어 (솔버, 파서, SQL 생성) | pytest + hypothesis |
| 통합 테스트 | API 레이어 (HTTP 요청/응답) | pytest + httpx |
| DB 테스트 | 모델 레이어 (CRUD, MV) | pytest + testcontainers (PostgreSQL) |
| 성능 테스트 | 피벗 쿼리 응답 시간 | locust |

---

## 금지 사항 (Forbidden) - 코드 리뷰 기준

- [ ] API 레이어에서 SQL 직접 실행
- [ ] 엔진 간 직접 import
- [ ] Core 소유 테이블에 쓰기 작업
- [ ] 동기 요청에서 60초 이상 블로킹
- [ ] Semaphore 없이 LLM API 호출
- [ ] 트랜잭션 없이 DB 쓰기
- [ ] 구조화되지 않은 로그 (print문)

## 필수 사항 (Required) - 코드 리뷰 기준

- [ ] 모든 엔진 함수에 타입 힌트
- [ ] 모든 비동기 작업에 타임아웃
- [ ] 모든 DB 쿼리에 org_id 필터 (RLS 보조)
- [ ] 모든 외부 호출에 에러 핸들링
- [ ] 모든 API 엔드포인트에 OpenAPI 문서화 (FastAPI 자동)

<!-- affects: 01_architecture/architecture-overview.md -->
<!-- requires-update: 없음 (이 문서가 코드 리뷰 기준) -->
