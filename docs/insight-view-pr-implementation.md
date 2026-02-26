# Insight View PR 구현 가이드

> **버전**: v3.4
> **작성일**: 2026-02-26
> **최종 수정**: 2026-02-27 (갭 수정 구현 완료 반영 — C-1/C-2/H-1/H-2/M-1/M-2/M-3)
> **상위 문서**: [Insight View 구현 설계서](./insight-view-implementation.md) (§15.6 PR 분리 가이드 참조)
> **목적**: 설계서의 PR1~PR8을 "컴파일/실행 단위"로 끊어, 바로 코드 리뷰 가능한 수준의 골격 제공
>
> **구현 시 의도적 변경 사항** (설계 → 실제):
>
> | 설계 (v3.3) | 실제 구현 | 사유 |
> | --- | --- | --- |
> | `org_id` | `tenant_id` | 기존 Weaver 코드베이스 컨벤션 통일 |
> | `app.current_org_id` | `app.current_tenant_id` | RLS 설정키 통일 |
> | Alembic 마이그레이션 | `insight_store.py` idempotent DDL | 외부 의존 최소화, 자동 스키마 생성 |
> | SQLAlchemy async session | asyncpg raw pool | 기존 Weaver 패턴 일관성 |
> | `core/errors.py` + `core/error_handler.py` | `core/insight_errors.py` (통합) | 파일 수 최소화 |
> | `core/authz.py` | `core/insight_auth.py` | 기존 `auth_service` 위임 패턴 |
> | `core/sql_normalize.py` | `services/sql_normalize.py` | services 레이어에 통합 |
> | `schemas/insight_logs.py` | `schemas/insight_schemas.py` | 전체 스키마 단일 파일 |
> | `services/query_log_store.py` | `services/insight_query_store.py` | naming convention 통일 |
> | `services/job_store.py` | `services/insight_job_store.py` | naming convention 통일 |
> | `core/redis_client.py` | `core/insight_redis.py` | 모듈 독립성 |
> | `worker/tasks/parse_task.py` | `worker/parse_task.py` | tasks 디렉토리 생략 |
> | `worker/tasks/impact_task.py` | `worker/impact_task.py` | tasks 디렉토리 생략 |
> | sqlglot 기반 SQL 파서 | regex 기반 파서 | 의존성 최소화, 충분한 정확도 |
> | `GET /impact` | `POST /impact` | request body로 복합 파라미터 전달 |

---

## 목차

1. [PR 의존성 트리](#pr-의존성-트리)
2. [PR1: DB 마이그레이션 (Alembic) + RLS + 인덱스](#pr1-db-마이그레이션)
3. [PR2: 공통 — trace_id + 에러 표준 + RLS 미들웨어](#pr2-공통)
4. [PR3: Auth → effective_org_id 표준 의존성](#pr3-auth)
5. [PR4: Ingest API + 멱등성 + write-fast](#pr4-ingest-api)
6. [PR5: Redis Job + Impact 202 + job 재사용](#pr5-redis-job)
7. [PR6: Worker — Parse Worker + Impact Worker](#pr6-worker)
8. [PR7: Impact Analysis Core — Analyzer + Scorer + Graph Builder](#pr7-impact-analysis-core)
9. [PR8: Accuracy Jump — Co-occur Matrix + KPI Mapping + Unified Node ID](#pr8-accuracy-jump)
10. [main.py 부트스트랩](#mainpy-부트스트랩)
11. [실전 위험 포인트 10선 + 방지책](#실전-위험-포인트)
12. [v1 정확도 한계와 v2 진화 경로](#v1-정확도-한계)

---

## PR 의존성 트리

```
PR-1 (DB: insight_store.py — idempotent DDL)
  └── PR-2 (공통: insight_errors.py + rls_session.py)
        └── PR-3 (Auth: insight_auth.py)
              └── PR-4 (Ingest: insight.py + schemas + query_store + normalize + idempotency)
                    └── PR-5 (Redis Job: insight_redis.py + insight_job_store.py)
                          └── PR-6 (Workers: parse_task.py + impact_task.py)
                                └── PR-7 (Analysis: query_log_analyzer + driver_scorer + impact_graph_builder)
                                      └── PR-8 (Accuracy: cooccur_matrix + kpi_metric_mapper + node_id)
```

| PR | 제목 | 핵심 산출물 | 검증 기준 | 상태 | 비고 |
| --- | --- | --- | --- | --- | --- |
| **PR-1** | DB 마이그레이션 | `insight_store.py` — idempotent DDL + RLS | 테이블 자동 생성, RLS 동작 | ✅ 95% | PARTITION 미사용 (의도적), 테이블 구조 설계 이상 |
| **PR-2** | 공통 인프라 | `insight_errors.py`, `rls_session.py` | 에러 응답 포맷, SET LOCAL 격리 | ✅ 98% | 파일 통합 (의도적), trace_middleware 기존 활용 |
| **PR-3** | Auth | `insight_auth.py` — `get_effective_tenant_id` | 토큰 없으면 401, tenant_id 추출 | ✅ 100% | 설계 의도 완전 구현 |
| **PR-4** | Ingest API | POST /logs, POST /logs:ingest | 멱등 중복제거, batch 기록 | ⚠️ 70% | PII regex 미구현, MAX_SQL_LENGTH 미검증, hash `[:32]` 미적용 |
| **PR-5** | Redis Job | POST /impact (202), GET /jobs/{id} | job 재사용, 상태 조회 | ✅ 100% | C-1 datasource_id 격리, C-2 cache-first, H-1 SETNX, M-1/M-2 TTL분리·heartbeat 갱신 — 모두 완료 |
| **PR-6** | Workers | `parse_task.py`, `impact_task.py` | parse_status 전이, graph cache 저장 | ✅ 95% | H-2 KpiMapper 연결 + 캐시 포맷 통일 완료; parse_mode/confidence 미저장만 잔존 |
| **PR-7** | Impact Analysis Core | `query_log_analyzer`, `driver_scorer`, `impact_graph_builder` | 50k 쿼리 → graph JSON, top driver 스코어 안정 | ✅ 90% | scorer 수식 100% 일치, DB 접근 asyncpg (의도적 변경) |
| **PR-8** | Accuracy Jump | `cooccur_matrix`, `kpi_metric_mapper`, `node_id` | co-occur 엣지, KPI↔metric, 통합 노드 ID | ✅ 100% | cooccur·node_id 전체 통합 완료; Query Subgraph `node_id.py` 적용, `meta.reason` 수정 |

---

## 구현 갭 분석 요약

> **분석일**: 2026-02-27 (최종 업데이트)
> **기준**: 설계서 v3.3 코드 스펙 vs 실제 구현 코드
> **범위**: PR1~PR8 전체

### 미구현 항목 (Critical)

| # | 설계 항목 | 설계 위치 | 실제 상태 | 영향도 |
| --- | --- | --- | --- | --- |
| 1 | **PII 마스킹 (EMAIL/PHONE/SSN regex)** | PR4 §4.2 `mask_pii()` | `sql_normalize.py`에 string literal/numeric만 구현, PII regex 없음 | 높음 — PII 유출 위험 |
| ~~2~~ | ~~**`heartbeat()` 함수**~~ | PR5 §5.2, PR6 §6.2 | ✅ **수정 완료** — `heartbeat()` 구현 + jobmap TTL 갱신 추가 (M-2 fix) | ~~중간~~ → 해소 |
| 3 | **Worker 큐 enqueue** | PR5 §5.3 `job_queue.enqueue()` | `insight.py`에서 `asyncio.create_task`로 즉시 실행 — 단일 서버 동작 | 중간 — 서버 재시작 시 job 소실 (M-3 startup cleanup으로 완화) |
| ~~4~~ | ~~**PR8 cooccur → graph_builder 통합**~~ | PR8 §8-5 | ✅ **구현 완료** — `cooccur.strength()` 우선 사용, `join_edges` fallback 포함 | ~~높음~~ → 해소 |
| ~~5~~ | ~~**PR8 unified node_id → graph_builder 통합**~~ | PR8 §8-5 | ✅ **구현 완료** — `kpi_node_id()`, `column_node_id_from_key()` 사용, 인라인 f-string 제거 | ~~중간~~ → 해소 |
| ~~6~~ | ~~**`load_kpi_definitions()` DB 로더**~~ | PR8 §8-2 | ✅ **구현 완료** — asyncpg로 `weaver.ontology_kpi_definitions` 조회, 테이블 미존재 시 graceful 처리 | ~~중간~~ → 해소 |
| ~~4′~~ | ~~**COUPLED 엣지 `meta.reason` 이름 불일치**~~ | PR8 §8-5 | ✅ **수정 완료** — `impact_graph_builder.py` line 165: `"cooccur"` → `"cooccur_matrix"` | ~~낮음~~ → 해소 |
| ~~5′~~ | ~~**Query Subgraph 빌더 `node_id.py` 미적용**~~ | PR8 §8-5 | ✅ **수정 완료** — `insight.py` `_parse_result_to_graph()`: `table_node_id()` + `column_node_id()` 적용 | ~~중간~~ → 해소 |
| 7 | **`MAX_SQL_LENGTH` 검증** | PR4 §4.4 (100KB 제한) | ✅ **구현 완료** — `insight_query_store.py:9,42-48`: `MAX_SQL_LENGTH = 100_000` + skip 로직 | ~~낮음~~ → 해소 |
| 8 | **멱등키 hash `[:32]` 절단** | PR4 §4.3 | ✅ **구현 완료** — `idempotency.py:15,29`: `hexdigest()[:32]` | ~~낮음~~ → 해소 |
| 9 | **`parse_mode`, `parse_confidence` 컬럼 UPDATE** | PR6 §6.1 | ✅ **구현 완료** — `parse_task.py:202-215`: `parse_mode=$9, parse_confidence=$10` | ~~중간~~ → 해소 |
| ~~10~~ | ~~**Impact 결과 별도 cache_key 저장**~~ | PR6 §6.2 Step 5 | ✅ **수정 완료** — `impact_task.py`: `_build_cache_key()` + `{"job_id":…,"result":…}` 래핑 저장; API cache-first 조회 추가 (C-2 fix) | ~~중간~~ → 해소 |
| ~~C-1~~ | ~~**`_jobmap_key`에 `datasource_id` 누락**~~ | `insight_job_store.py` | ✅ **수정 완료** — `datasource_id` 포함한 새 시그니처로 교체 | ~~치명~~ → 해소 |
| ~~H-1~~ | ~~**`get_or_create_job()` 비원자적 생성**~~ | `insight_job_store.py` | ✅ **수정 완료** — `SET NX` 원자적 생성 + tentative job 정리 로직 | ~~높음~~ → 해소 |
| ~~M-1~~ | ~~**TTL 상수 미분리**~~ | `insight_job_store.py` | ✅ **수정 완료** — `TTL_QUEUED=600 / TTL_RUNNING=3600 / TTL_DONE=3600 / TTL_FAILED=300` | ~~중간~~ → 해소 |
| ~~M-3~~ | ~~**서버 재시작 시 `running` job 영구 대기**~~ | `main.py` | ✅ **수정 완료** — startup 이벤트에서 `running` → `failed` 마킹 | ~~중간~~ → 해소 |

### 의도적 변경 (Accepted Deviation)

| 설계 | 실제 | 사유 | 평가 |
| --- | --- | --- | --- |
| `org_id` 전체 | `tenant_id` 전체 | Weaver 기존 컨벤션 | ✅ 합리적 |
| SQLAlchemy `AsyncSession` | asyncpg raw pool | 기존 패턴 일관성 | ✅ 합리적 |
| Alembic 마이그레이션 | idempotent DDL | 외부 의존 최소화 | ✅ 합리적 |
| sqlglot SQL 파서 | regex 기반 파서 | 의존성 최소화 | ⚠️ 정확도 trade-off 존재 |
| `GET /impact` (Query param) | `POST /impact` (Body) | 복합 파라미터 전달 | ✅ 합리적 |
| PARTITION BY LIST | 단일 테이블 | 초기 단순화 | ✅ 향후 확장 가능 |
| 파일 분리 (errors+handler) | 단일 파일 통합 | 파일 수 최소화 | ✅ 합리적 |
| `progress_pct` 필드명 | `progress` 필드명 | 간소화 | ✅ 사소한 차이 |

### 우선 수정 권장 순서

1. ~~**[P0]** Worker 큐 enqueue 연결 (PR5 §5.3)~~ — `asyncio.create_task` + startup cleanup으로 단일서버 운영 가능 (외부 큐는 v2 과제)
2. **[P0]** PII regex 추가 (PR4 §4.2) — 보안 필수 (미완료)
3. ~~**[P1]** Impact 결과 Redis cache 저장 (PR6 §6.2)~~ — ✅ 완료 (C-2 fix)
4. ~~**[P1]** Query Subgraph 빌더 `node_id.py` 적용~~ — ✅ 완료 (`_parse_result_to_graph` 수정)
5. ~~**[P2]** heartbeat 구현 + impact_task 호출~~ — ✅ 완료 (M-2 fix + jobmap TTL 갱신)
6. ~~**[P2]** parse_mode/confidence 저장~~ — ✅ 완료 (`parse_task.py:202-215`)
7. ~~**[P2]** COUPLED `meta.reason` 이름 통일~~ — ✅ 완료 (`"cooccur_matrix"` 적용)
8. ~~**[P3]** MAX_SQL_LENGTH, hash 절단~~ — ✅ 완료 (`insight_query_store.py`, `idempotency.py`)
9. ~~**[P3]** load_kpi_definitions DB 로더~~ — ✅ 완료 (KpiMapper → impact pipeline 연결 포함)
10. ~~**[P1]** PR8 cooccur + node_id → graph_builder 통합~~ — ✅ 완료

**잔존 미완료**: PII regex (보안 필수), 외부 큐 (운영 확장성 필요 시)

---

## PR1: DB 마이그레이션

> **파일**: `services/weaver/app/services/insight_store.py` (181 lines)
> **의존**: 없음 (최우선 머지)
> **v3.4 변경**: Alembic → idempotent DDL (`CREATE TABLE IF NOT EXISTS`), `org_id` → `tenant_id`, PARTITION BY LIST 미사용 (단순 테이블), SQLAlchemy → asyncpg raw pool.

### 1.1 InsightStore (idempotent DDL)

```python
# services/weaver/app/services/insight_store.py (실제 구현)
from __future__ import annotations

import logging

from app.core.config import settings
from app.services.resilience import CircuitBreakerOpenError, SimpleCircuitBreaker, with_retry

logger = logging.getLogger("weaver.insight_store")


class InsightStoreUnavailableError(RuntimeError):
    pass


class InsightStore:
    """Manages the Insight View tables (asyncpg pool, idempotent DDL migration).

    Pattern follows PostgresMetadataStore: lazy pool init, circuit breaker,
    ``CREATE TABLE IF NOT EXISTS`` for zero-downtime schema creation.
    """

    _DB_SCHEMA = "weaver"

    def __init__(self) -> None:
        self._pool = None
        self._breaker = SimpleCircuitBreaker(failure_threshold=3, reset_timeout_seconds=20.0)

    async def _get_pool(self):
        try:
            self._breaker.preflight()
        except CircuitBreakerOpenError as exc:
            raise InsightStoreUnavailableError(str(exc)) from exc
        if self._pool is not None:
            return self._pool
        dsn = settings.postgres_dsn
        if not dsn:
            raise InsightStoreUnavailableError("POSTGRES_DSN is required for insight store")
        import asyncpg

        async def _create():
            return await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=5,
                server_settings={"search_path": f"{self._DB_SCHEMA},public"},
            )

        try:
            self._pool = await with_retry(_create, retries=2, base_delay_seconds=0.05)
            self._breaker.on_success()
        except Exception as exc:
            self._breaker.on_failure()
            raise InsightStoreUnavailableError(str(exc)) from exc
        await self._migrate()
        return self._pool

    async def get_pool(self):
        return await self._get_pool()

    async def _migrate(self) -> None:
        pool = self._pool
        async with pool.acquire() as conn:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self._DB_SCHEMA}")

            # 1. insight_ingest_batches
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS weaver.insight_ingest_batches (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'oracle',
                    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    row_count INT NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'accepted',
                    error_message TEXT
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iib_tenant "
                "ON weaver.insight_ingest_batches(tenant_id, received_at DESC)"
            )

            # 2. insight_query_logs
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS weaver.insight_query_logs (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    datasource_id TEXT NOT NULL,
                    query_id TEXT NOT NULL,
                    raw_sql TEXT NOT NULL,
                    normalized_sql TEXT NOT NULL DEFAULT '',
                    sql_hash TEXT NOT NULL DEFAULT '',
                    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    duration_ms INT,
                    user_id TEXT,
                    source TEXT NOT NULL DEFAULT 'oracle',
                    batch_id BIGINT,
                    parse_status TEXT NOT NULL DEFAULT 'pending',
                    parse_warnings JSONB DEFAULT '[]'::jsonb,
                    parse_errors JSONB DEFAULT '[]'::jsonb,
                    parsed_tables JSONB DEFAULT '[]'::jsonb,
                    parsed_joins JSONB DEFAULT '[]'::jsonb,
                    parsed_predicates JSONB DEFAULT '[]'::jsonb,
                    parsed_select JSONB DEFAULT '[]'::jsonb,
                    parsed_group_by JSONB DEFAULT '[]'::jsonb
                )
            """)
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_iql_tenant_query "
                "ON weaver.insight_query_logs(tenant_id, query_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iql_tenant_ds_time "
                "ON weaver.insight_query_logs(tenant_id, datasource_id, executed_at DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iql_parse_status "
                "ON weaver.insight_query_logs(parse_status) WHERE parse_status = 'pending'"
            )

            # 3. insight_driver_scores
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS weaver.insight_driver_scores (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    datasource_id TEXT NOT NULL,
                    kpi_fingerprint TEXT NOT NULL,
                    column_key TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'DRIVER',
                    score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
                    scoring_config JSONB NOT NULL DEFAULT
                        '{"decay":"step","weights":{"usage":0.45}}'::jsonb,
                    formula_version TEXT NOT NULL DEFAULT 'v1',
                    graph_json JSONB,
                    time_range TEXT NOT NULL DEFAULT '30d',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    expires_at TIMESTAMPTZ
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ids_tenant_kpi "
                "ON weaver.insight_driver_scores(tenant_id, kpi_fingerprint, created_at DESC)"
            )

            # RLS policies (tenant_id 기반)
            for tbl in ("insight_ingest_batches", "insight_query_logs",
                        "insight_driver_scores"):
                await conn.execute(f"ALTER TABLE weaver.{tbl} ENABLE ROW LEVEL SECURITY")
                await conn.execute(f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_policies
                            WHERE tablename = '{tbl}'
                              AND policyname = '{tbl}_tenant_isolation'
                        ) THEN
                            EXECUTE format(
                                'CREATE POLICY {tbl}_tenant_isolation ON weaver.{tbl} '
                                'USING (tenant_id = current_setting(''app.current_tenant_id'', true))'
                            );
                        END IF;
                    END
                    $$
                """)

            logger.info("InsightStore migration complete (3 tables + RLS)")


insight_store = InsightStore()
```

> **v3.4 Note**: 파티션(`PARTITION BY LIST`) 및 `partition_manager.py`는 미구현. 단일 테이블로 운영하며, 향후 트래픽 증가 시 파티션 전환 예정.

### 1.2 PR1 체크리스트

- [x] 서버 기동 시 3개 테이블 자동 생성 (`CREATE TABLE IF NOT EXISTS`)
- [x] RLS 정책 동작: `SET LOCAL app.current_tenant_id = 'tenant_A'` 후 다른 tenant 데이터 0건
- [x] `UNIQUE(tenant_id, query_id)` 중복 INSERT 시 `ON CONFLICT DO NOTHING`
- [x] Circuit breaker: DB 연결 실패 3회 → `InsightStoreUnavailableError`
- [x] 테스트: `test_pr1_insight_store.py` 통과

---

## PR2: 공통

> 공통 인프라: 에러 모델 + RLS 세션 래퍼 (단일 파일 `insight_errors.py`에 통합)
> **v3.4 변경**: `core/errors.py` + `core/error_handler.py` → `core/insight_errors.py` 통합. `TraceIdMiddleware` → `main.py`의 `request_context_middleware` 활용. SQLAlchemy → asyncpg.

### 2.1 InsightError + 에러 핸들러 (통합)

> **파일**: `services/weaver/app/core/insight_errors.py`

```python
# services/weaver/app/core/insight_errors.py (실제 구현)
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class InsightError(Exception):
    """Standardized error for Insight View endpoints.

    Attributes:
        retryable: If True, frontend may auto-retry after ``poll_after_ms``.
        hint: Human-readable guidance for recovery.
    """

    status_code: int
    error_code: str
    error_message: str
    retryable: bool = False
    hint: str = ""
    poll_after_ms: int = 0


async def insight_error_handler(request: Request, exc: InsightError) -> JSONResponse:
    """FastAPI exception handler registered on ``InsightError``."""
    trace_id = getattr(request.state, "request_id", None) or \
        request.headers.get("X-Request-Id", "")
    body: dict = {
        "error": {
            "code": exc.error_code,
            "message": exc.error_message,
            "retryable": exc.retryable,
            "hint": exc.hint,
        },
        "trace_id": trace_id,
    }
    if exc.poll_after_ms:
        body["poll_after_ms"] = exc.poll_after_ms
    return JSONResponse(status_code=exc.status_code, content=body)
```

> **v3.4 Note**: trace_id는 `main.py`의 `request_context_middleware`가 `request.state.request_id`로 부여한다. 별도 `TraceIdMiddleware` 클래스 불필요.

### 2.2 RLS `SET LOCAL` 세션 래퍼

> **파일**: `services/weaver/app/core/rls_session.py`
>
> 핵심: 트랜잭션 범위에서만 `tenant_id`를 설정하고, 커밋/롤백 후 자동 해제.
> 커넥션 풀에 세팅이 남지 않으므로 **테넌트 데이터 유출 방지**. (설계서 §7.7)

```python
# services/weaver/app/core/rls_session.py (실제 구현)
from __future__ import annotations

from contextlib import asynccontextmanager


@asynccontextmanager
async def rls_session(pool, tenant_id: str):
    """Acquire a connection with RLS ``SET LOCAL`` scoped to a transaction.

    Usage::

        async with rls_session(pool, tenant_id) as conn:
            rows = await conn.fetch("SELECT * FROM weaver.insight_query_logs")

    The ``SET LOCAL`` ensures ``app.current_tenant_id`` is visible only within
    this transaction and automatically reverts when the connection returns to the
    pool — preventing cross-tenant data leaks in pgbouncer / connection-pool
    scenarios.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, true)",
                tenant_id,
            )
            yield conn
```

### 2.3 PR2 체크리스트

- [x] `InsightError(status_code=400, error_code="TEST", error_message="test")` → JSON 응답
- [x] `X-Request-Id` 헤더 → 응답에 동일 값 전파 (main.py middleware)
- [x] `rls_session` 내에서 `current_setting('app.current_tenant_id')` == tenant_id
- [x] `rls_session` 종료 후 설정 자동 해제 (트랜잭션 스코프)
- [x] 테스트: `test_pr2_common.py` 통과

---

## PR3: Auth

> **파일**: `services/weaver/app/core/insight_auth.py`
> **v3.4 변경**: `core/authz.py` → `core/insight_auth.py`. 기존 `auth_service`에 위임하여 JWT 검증. `org_id` → `tenant_id`.

```python
# services/weaver/app/core/insight_auth.py (실제 구현)
from __future__ import annotations

from typing import List

from fastapi import Depends, Request

from app.core.auth import auth_service, CurrentUser


async def get_current_insight_user(request: Request) -> CurrentUser:
    """Extract and verify the JWT bearer token from the request."""
    auth_header = request.headers.get("Authorization")
    return auth_service.verify_token(auth_header)


async def get_effective_tenant_id(
    user: CurrentUser = Depends(get_current_insight_user),
) -> str:
    """Return the tenant_id from the verified JWT — used for RLS scoping."""
    return user.tenant_id


def require_insight_role(*allowed_roles: str):
    """Factory that returns a FastAPI dependency checking the user's role."""

    async def _check(
        user: CurrentUser = Depends(get_current_insight_user),
    ) -> CurrentUser:
        auth_service.requires_role(user, list(allowed_roles))
        return user

    return Depends(_check)
```

### PR3 체크리스트

- [x] 토큰 없이 요청 → 401
- [x] 정상 토큰 → `get_effective_tenant_id` 반환값 == `user.tenant_id`
- [x] `require_insight_role("admin")` + 권한 없는 토큰 → 403
- [x] 테스트: `test_pr3_auth.py` 통과

---

## PR4: Ingest API

> POST `/api/insight/logs` + `/api/insight/logs:ingest`
> write-fast: 저장 우선, 파싱은 Worker에 위임 (설계서 §5.8)
> **v3.4 변경**: 스키마 파일 `insight_logs.py` → `insight_schemas.py`, 클래스명 간소화, `core/sql_normalize.py` → `services/sql_normalize.py`, `query_log_store.py` → `insight_query_store.py` (asyncpg), `org_id` → `tenant_id`

### 4.1 Pydantic 스키마

> **파일**: `services/weaver/app/api/schemas/insight_schemas.py`

```python
# services/weaver/app/api/schemas/insight_schemas.py (실제 구현)
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Ingest request ───────────────────────────────────────────

class LogItem(BaseModel):
    raw_sql: str = Field(..., min_length=1)
    datasource_id: str = Field(..., min_length=1)
    executed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None


class IngestLogsRequest(BaseModel):
    logs: list[LogItem] = Field(..., min_length=1, max_length=5000)
    source: str = Field(default="oracle")


# ── Ingest response ──────────────────────────────────────────

class IngestLogsResponse(BaseModel):
    inserted: int
    deduped: int
    batch_id: Optional[int] = None
    trace_id: str = ""


# ── Impact request / response ────────────────────────────────

class ImpactRequest(BaseModel):
    datasource_id: str = Field(..., min_length=1)
    kpi_fingerprint: str = Field(..., min_length=1)
    time_range: str = Field(default="30d")
    top: int = Field(default=50, ge=1, le=200)


class ImpactAcceptedResponse(BaseModel):
    """202 Accepted — job was created or is already running."""
    job_id: str
    status: str = "queued"
    poll_url: str = ""
    poll_after_ms: int = 2000
    trace_id: str = ""


class ImpactCachedResponse(BaseModel):
    """200 OK — cached result available."""
    job_id: str
    status: str = "done"
    graph: Any = None
    trace_id: str = ""


# ── Job status response ─────────────────────────────────────

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    error: str = ""
    graph: Any = None
    trace_id: str = ""
```

### 4.2 SQL 정규화 + PII 마스킹

> **파일**: `services/weaver/app/core/sql_normalize.py`
> §5.5.1 불변조건: `normalized_sql`은 항상 생성해야 한다.

```python
import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{6}[-]?\d{7}\b")
_STRING_LITERAL_RE = re.compile(r"'[^']*'")


def mask_pii(sql: str) -> str:
    """PII 패턴을 마스킹한다."""
    sql = _EMAIL_RE.sub("'[EMAIL]'", sql)
    sql = _PHONE_RE.sub("'[PHONE]'", sql)
    sql = _SSN_RE.sub("'[SSN]'", sql)
    sql = _STRING_LITERAL_RE.sub("?", sql)
    return sql


def normalize_sql(sql: str) -> str:
    """최소 정규화: PII 마스킹 + 공백 정규화.

    이 함수는 sqlglot 없이도 동작해야 한다 (write-fast 경로).
    """
    masked = mask_pii(sql)
    return " ".join(masked.split())
```

### 4.3 멱등키 생성

> **파일**: `services/weaver/app/services/idempotency.py`
> 설계서 §2.5.2: 실시간 경로 = request_id 포함, 배치 경로 = 5분 버킷.

```python
import hashlib
from datetime import datetime, timezone


def _time_bucket_5m(iso_ts: str) -> str:
    """ISO 타임스탬프를 5분 버킷으로 라운드."""
    dt = datetime.fromisoformat(
        iso_ts.replace("Z", "+00:00")
    ).astimezone(timezone.utc)
    minute = (dt.minute // 5) * 5
    return dt.replace(minute=minute, second=0, microsecond=0).isoformat()


def realtime_query_id(
    org_id: str, datasource: str, normalized_sql: str, request_id: str,
) -> str:
    """실시간 경로 멱등키: request_id 포함으로 정밀 dedupe."""
    raw = f"{org_id}|{datasource}|{normalized_sql}|{request_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def batch_query_id(
    org_id: str, datasource: str, normalized_sql: str, executed_at_iso: str,
) -> str:
    """배치 경로 멱등키: 5분 버킷으로 과도 반복 중복 제거."""
    raw = f"{org_id}|{datasource}|{normalized_sql}|{_time_bucket_5m(executed_at_iso)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
```

### 4.4 Store: write-fast 저장

> **파일**: `services/weaver/app/services/query_log_store.py`

```python
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .idempotency import realtime_query_id
from ..core.sql_normalize import normalize_sql

MAX_SQL_LENGTH = 100_000


async def insert_logs(
    session: AsyncSession,
    org_id: str,
    ingest_batch_id: str,
    entries: list[dict],
    *,
    is_batch: bool = False,
) -> tuple[int, int, int, list]:
    """write-fast: 최소 검증 후 즉시 저장. 파싱은 Worker에 위임.

    Returns:
        (accepted, deduped, rejected, errors)
    """
    accepted = deduped = rejected = 0
    errors: list[dict] = []

    for i, e in enumerate(entries):
        sql_raw = e["sql"]

        # ── 검증 ──
        if len(sql_raw) > MAX_SQL_LENGTH:
            rejected += 1
            errors.append({"index": i, "reason": "SQL too large"})
            continue

        normalized = e.get("normalized_sql") or normalize_sql(sql_raw)
        if not normalized:
            rejected += 1
            errors.append({"index": i, "reason": "normalized_sql empty"})
            continue

        # ── 멱등키 ──
        qid = realtime_query_id(
            org_id, e["datasource"], normalized, e.get("request_id", ""),
        )

        # ── 중복 체크 (ON CONFLICT 권장, 아래는 안전한 체크 버전) ──
        exists = await session.execute(
            text(
                "SELECT 1 FROM insight_query_logs "
                "WHERE org_id = :org AND query_id = :qid LIMIT 1"
            ),
            {"org": org_id, "qid": qid},
        )
        if exists.first():
            deduped += 1
            continue

        # ── write-fast INSERT (parse_status = pending) ──
        await session.execute(
            text("""
            INSERT INTO insight_query_logs (
              org_id, datasource, query_id, request_id, trace_id, dialect,
              executed_at, status, duration_ms, row_count, error_code,
              user_id, user_role, nl_query, intent, tags,
              sql_raw_enc, normalized_sql, result_schema,
              parse_status, ingest_batch_id
            ) VALUES (
              :org_id, :datasource, :query_id, :request_id, :trace_id, :dialect,
              :executed_at::timestamptz, :status, :duration_ms, :row_count,
              :error_code,
              :user_id, :user_role, :nl_query, :intent, :tags,
              NULL, :normalized_sql, :result_schema::jsonb,
              'pending', :ingest_batch_id
            )
            """),
            {
                "org_id": org_id,
                "datasource": e["datasource"],
                "query_id": qid,
                "request_id": e.get("request_id"),
                "trace_id": e.get("trace_id"),
                "dialect": e.get("dialect", "postgres"),
                "executed_at": e["executed_at"],
                "status": e["status"],
                "duration_ms": e.get("duration_ms"),
                "row_count": e.get("row_count"),
                "error_code": e.get("error_code"),
                "user_id": (e.get("user") or {}).get("user_id"),
                "user_role": (e.get("user") or {}).get("role"),
                "nl_query": e.get("nl_query"),
                "intent": e.get("intent"),
                "tags": e.get("tags"),
                "normalized_sql": normalized,
                "result_schema": json.dumps(e.get("result_schema"))
                    if e.get("result_schema") else None,
                "ingest_batch_id": ingest_batch_id,
            },
        )
        accepted += 1

    return accepted, deduped, rejected, errors
```

### 4.5 Router: POST /api/insight/logs

> **파일**: `services/weaver/app/api/insight.py`

```python
import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from .schemas.insight_logs import IngestRequest, IngestResponse
from ..core.authz import get_effective_org_id
from ..core.rls_session import rls_session
from ..services.query_log_store import insert_logs

router = APIRouter(prefix="/api/insight", tags=["insight"])


@router.post("/logs", response_model=IngestResponse)
async def ingest_logs(
    body: IngestRequest,
    request: Request,
    org_id: str = Depends(get_effective_org_id),
):
    """쿼리 로그 인제스트 (write-fast).

    저장 후 Parse Worker 큐에 자동 등록된다.
    """
    ingest_batch_id = str(uuid.uuid4())

    sf = request.app.state.session_factory
    async with rls_session(sf, org_id) as session:
        accepted, deduped, rejected, errors = await insert_logs(
            session=session,
            org_id=org_id,
            ingest_batch_id=ingest_batch_id,
            entries=[e.model_dump() for e in body.entries],
        )

        # insight_ingest_batches 기록
        await session.execute(
            text(
                "INSERT INTO insight_ingest_batches "
                "(org_id, ingest_batch_id, source, entry_count, "
                " accepted, deduped, rejected, trace_id) "
                "VALUES (:org, :bid, 'oracle', :cnt, :a, :d, :r, :t)"
            ),
            {
                "org": org_id,
                "bid": ingest_batch_id,
                "cnt": len(body.entries),
                "a": accepted,
                "d": deduped,
                "r": rejected,
                "t": request.state.trace_id,
            },
        )

    # TODO: accepted > 0 이면 Parse Worker 큐에 enqueue
    # await request.app.state.parse_queue.enqueue(...)

    return IngestResponse(
        accepted=accepted,
        deduped=deduped,
        rejected=rejected,
        errors=errors,
        ingest_batch_id=ingest_batch_id,
    )
```

> `/logs:ingest`는 동일 `insert_logs` 로직에서 `is_batch=True`로 호출하여 `batch_query_id` 사용.

### PR4 체크리스트

- [x] ~~100건 초과 배치 → 400~~ 실제: `max_length=5000` (설계 100 → 구현 5000으로 상향)
- [ ] **❌ 100KB 초과 SQL → rejected** — `MAX_SQL_LENGTH` 검증 미구현
- [x] 동일 `query_id` 2회 전송 → `deduped=1` — `ON CONFLICT DO NOTHING` 구현
- [x] `normalized_sql` 항상 비어있지 않음 — `normalize_sql()` + `mask_pii()` 체인 동작
- [x] `ingest_batches` 테이블에 기록 존재 — `insert_batch_record()` 구현
- [x] RLS: tenant_A 토큰으로 tenant_B 데이터 접근 불가
- [ ] **❌ PII regex (EMAIL/PHONE/SSN)** — `mask_pii()`에 string/numeric literal만 있음, PII 패턴 누락
- [ ] **⚠️ 멱등키 hash 절단** — 설계 `[:32]` vs 구현 64자 전체
- [ ] **⚠️ 멱등키 파라미터 순서** — 설계 `(org_id, datasource, normalized_sql, ...)` vs 구현 `(normalized_sql, tenant_id, datasource_id, ...)`

---

## PR5: Redis Job

> Redis 기반 Job 상태 관리 + Impact Graph 202 패턴 (설계서 §4.9.2)

### 5.1 Redis 클라이언트

> **파일**: `services/weaver/app/core/redis_client.py`

```python
import redis.asyncio as redis


def create_redis(url: str) -> redis.Redis:
    """decode_responses=True로 문자열 자동 디코딩."""
    return redis.from_url(url, decode_responses=True)
```

### 5.2 Job Store

> **파일**: `services/weaver/app/services/job_store.py`

```python
import time
import uuid
from typing import Any

JOB_TTL_RUNNING_S = 600   # 10분 (heartbeat 연장)
JOB_TTL_DONE_S = 600      # 10분
JOB_TTL_FAILED_S = 300    # 5분


def build_job_key(
    org_id: str,
    kpi_fp: str,
    time_range: str,
    top_drivers: int,
    analysis_version: str,
) -> str:
    """동일 분석 요청을 식별하는 dedupe 키."""
    return (
        f"insight:jobkey:{org_id}:{kpi_fp}"
        f":{time_range}:{top_drivers}:{analysis_version}"
    )


def _jobmap_key(job_key: str) -> str:
    return f"insight:jobmap:{job_key}"


def _job_state_key(job_id: str) -> str:
    return f"insight:job:{job_id}"


async def get_or_create_job(
    redis,
    job_key: str,
    trace_id: str,
    meta: dict,
) -> tuple[str, bool]:
    """job_key로 기존 job을 찾거나 신규 생성한다.

    Returns:
        (job_id, is_new_job)
    """
    mkey = _jobmap_key(job_key)

    # 1) 기존 job 조회
    existing = await redis.get(mkey)
    if existing:
        return existing, False

    # 2) 신규 job 생성
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = int(time.time() * 1000)

    await redis.hset(
        _job_state_key(job_id),
        mapping={
            "status": "queued",
            "progress_pct": "0",
            "poll_after_ms": "800",
            "created_at": str(now),
            "updated_at": str(now),
            "trace_id": trace_id,
            **{f"meta:{k}": str(v) for k, v in meta.items()},
        },
    )
    await redis.expire(_job_state_key(job_id), JOB_TTL_RUNNING_S)

    # SETNX로 경쟁 조건 방어
    ok = await redis.set(mkey, job_id, ex=JOB_TTL_RUNNING_S, nx=True)
    if not ok:
        # 다른 요청이 먼저 생성
        other = await redis.get(mkey)
        return other or job_id, False

    return job_id, True


async def get_job(redis, job_id: str) -> dict | None:
    """job HASH를 조회한다."""
    h = await redis.hgetall(_job_state_key(job_id))
    return h or None


async def update_job(redis, job_id: str, **fields: Any) -> None:
    """job 필드를 업데이트하고, running이면 TTL을 연장한다."""
    now = int(time.time() * 1000)
    fields["updated_at"] = str(now)
    await redis.hset(
        _job_state_key(job_id),
        mapping={k: str(v) for k, v in fields.items()},
    )
    status = fields.get("status")
    if status in ("running", "queued"):
        await redis.expire(_job_state_key(job_id), JOB_TTL_RUNNING_S)


async def finish_job(
    redis,
    job_id: str,
    status: str,
    ttl_s: int,
    **fields: Any,
) -> None:
    """job을 완료 상태로 전이하고 TTL을 설정한다."""
    await update_job(redis, job_id, status=status, **fields)
    await redis.expire(_job_state_key(job_id), ttl_s)


async def heartbeat(redis, job_key: str, job_id: str) -> None:
    """Worker가 30초마다 호출. running 상태의 TTL을 연장한다."""
    pipe = redis.pipeline()
    pipe.expire(_job_state_key(job_id), JOB_TTL_RUNNING_S)
    pipe.expire(_jobmap_key(job_key), JOB_TTL_RUNNING_S)
    await pipe.execute()
```

### 5.3 Impact API (캐시 히트/미스 + 202)

> **파일**: `services/weaver/app/api/insight.py` (추가)

```python
from fastapi import Query
from fastapi.responses import JSONResponse

from ..core.authz import get_effective_org_id
from ..core.errors import InsightError
from ..services.job_store import build_job_key, get_or_create_job, get_job


ANALYSIS_VERSION = "2026-02-26.1"  # TODO: settings에서 관리


@router.get("/impact")
async def get_impact(
    request: Request,
    kpi_fingerprint: str = Query(...),
    time_range: str = Query("30d"),
    top_drivers: int = Query(20, ge=1, le=50),
    org_id: str = Depends(get_effective_org_id),
):
    """KPI 영향 그래프 조회.

    - 캐시 히트 → 200
    - 캐시 미스 → job 생성/재사용 → 202
    """
    rd = request.app.state.redis

    # 1) 그래프 캐시 확인
    cache_key = (
        f"insight:{org_id}:impact:{kpi_fingerprint}"
        f":{time_range}:{top_drivers}:{ANALYSIS_VERSION}"
    )
    cached = await rd.get(cache_key)
    if cached:
        import json
        result = json.loads(cached)
        result["meta"]["cache_hit"] = True
        result["meta"]["cache_ttl_remaining_s"] = await rd.ttl(cache_key)
        return JSONResponse(status_code=200, content=result)

    # 2) Job 생성/재사용
    job_key = build_job_key(
        org_id, kpi_fingerprint, time_range, top_drivers, ANALYSIS_VERSION,
    )
    job_id, created = await get_or_create_job(
        redis=rd,
        job_key=job_key,
        trace_id=request.state.trace_id,
        meta={
            "org_id": org_id,
            "kpi_fp": kpi_fingerprint,
            "time_range": time_range,
            "top_drivers": top_drivers,
        },
    )

    if created:
        # 3) Worker 큐에 enqueue
        await request.app.state.job_queue.enqueue(
            "insight.impact.build",
            {
                "job_id": job_id,
                "job_key": job_key,
                "org_id": org_id,
                "kpi_fp": kpi_fingerprint,
                "time_range": time_range,
                "top_drivers": top_drivers,
            },
        )

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "queued",
            "poll_after_ms": 800,
            "reused": not created,
        },
    )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, request: Request):
    """Job 상태 조회."""
    rd = request.app.state.redis
    h = await get_job(rd, job_id)
    if not h:
        raise InsightError(
            "JOB_NOT_FOUND", f"Job not found: {job_id}",
            status=404, retryable=False,
        )

    return {
        "job_id": job_id,
        "status": h.get("status"),
        "progress_pct": int(h.get("progress_pct", "0")),
        "poll_after_ms": int(h.get("poll_after_ms", "800")),
        "created_at": h.get("created_at"),
        "completed_at": h.get("completed_at"),
        "result_url": h.get("result_url"),
        "error": h.get("error_message"),
    }
```

### PR5 체크리스트

- [x] **✅ 캐시 히트 → 200** — `_build_cache_key()` cache-first 조회 + `cache_hit=true` 메타 반환 (C-2 fix)
- [x] 캐시 미스 → 202 + `job_id` 반환 — `POST /impact` 구현
- [x] 동일 조건 재요청 → 같은 `job_id` — jobmap 키로 dedup 구현 + `datasource_id` 격리 (C-1 fix)
- [x] `GET /jobs/{unknown}` → 404 — `get_job` 조회 + 404 반환
- [x] job 상태에 `progress`, `poll_after_ms` 포함 — 필드명 `progress` (설계: `progress_pct`)
- [x] **✅ `heartbeat()` 함수** — `insight_job_store.py` 구현 + jobmap TTL 동시 갱신 (M-2 fix)
- [x] **✅ TTL 분리** — `TTL_QUEUED=600 / TTL_RUNNING=3600 / TTL_DONE=3600 / TTL_FAILED=300` (M-1 fix)
- [x] **✅ SET NX 경쟁조건 방어** — `rd.set(map_key, job_id, nx=True, ex=TTL_RUNNING)` 원자적 생성 (H-1 fix)
- [ ] **⚠️ job_id 포맷** — 설계: `job_{uuid[:12]}` → 구현: `uuid4().hex` (32자) — 사소한 차이, 기능 영향 없음
- [x] **✅ Worker 실행** — `asyncio.create_task(_run_impact_job(...))` 즉시 실행 + startup cleanup (M-3 fix)

---

## PR6: Worker

> 큐 구현체 중립: Celery/RQ/Arq 어디든 `handle(payload)` 하나만 연결하면 동작.

### 6.1 Parse Worker

> **파일**: `services/weaver/app/worker/tasks/parse_task.py`

```python
from sqlalchemy import text


async def run_parse_task(app, payload: dict):
    """Q1: insight.parse — 로그 파싱 및 parsed_* 업데이트.

    parse_status: pending → parsed | fallback | failed
    """
    org_id = payload["org_id"]
    row_id = payload["row_id"]
    dialect = payload.get("dialect", "postgres")

    async with app.state.session_factory() as session:
        async with session.begin():
            await session.execute(
                "SELECT set_config('app.current_org_id', :org, true)",
                {"org": org_id},
            )

            row = (
                await session.execute(
                    text(
                        "SELECT normalized_sql "
                        "FROM insight_query_logs "
                        "WHERE org_id = :org AND id = :id"
                    ),
                    {"org": org_id, "id": row_id},
                )
            ).first()
            if not row:
                return

            normalized_sql = row[0]

            # ── sqlglot 파싱 시도 ──
            from ..core.sql_parser import parse_sql  # noqa: lazy import
            result = parse_sql(normalized_sql, dialect=dialect)

            # ── parse_status 결정 ──
            if result.mode == "primary":
                parse_status = "parsed"
            elif result.mode == "warn":
                parse_status = "parsed"
            elif result.mode == "fallback":
                parse_status = "fallback"
            else:
                parse_status = "failed"

            # fallback인데 테이블도 못 뽑았으면 failed
            if parse_status == "fallback" and not result.tables:
                parse_status = "failed"

            # ── DB 업데이트 ──
            await session.execute(
                text("""
                UPDATE insight_query_logs
                SET parse_status     = :ps,
                    parse_mode       = :pm,
                    parse_confidence = :pc,
                    parse_warnings   = :pw,
                    parse_errors     = :pe,
                    parsed_tables    = :pt,
                    parsed_joins     = :pj::jsonb,
                    parsed_predicates = :pp::jsonb,
                    parsed_select    = :psel::jsonb,
                    parsed_group_by  = :pg
                WHERE org_id = :org AND id = :id
                """),
                {
                    "org": org_id,
                    "id": row_id,
                    "ps": parse_status,
                    "pm": result.mode,
                    "pc": result.confidence,
                    "pw": result.warnings or [],
                    "pe": result.errors or [],
                    "pt": [t["name"] for t in (result.tables or [])],
                    "pj": result.joins_json,
                    "pp": result.predicates_json,
                    "psel": result.select_json,
                    "pg": result.group_by_columns or [],
                },
            )
```

### 6.2 Impact Worker

> **파일**: `services/weaver/app/worker/tasks/impact_task.py`

```python
import json
import time

from ..services.job_store import (
    update_job,
    finish_job,
    heartbeat,
    JOB_TTL_DONE_S,
    JOB_TTL_FAILED_S,
)


async def run_impact_task(app, payload: dict):
    """Q2: insight.impact — KPI별 Impact Graph + Driver Scoring 생성."""
    rd = app.state.redis
    job_id = payload["job_id"]
    job_key = payload["job_key"]
    org_id = payload["org_id"]
    kpi_fp = payload["kpi_fp"]
    time_range = payload["time_range"]
    top = payload["top_drivers"]

    try:
        await update_job(rd, job_id, status="running", progress_pct=10)

        # ── Step 1: query_logs 로드 ──
        # parsed_status != 'pending' 우선, time_range 필터
        await update_job(rd, job_id, progress_pct=20)
        await heartbeat(rd, job_key, job_id)

        # TODO: query_log_analyzer.load_parsed_logs(org_id, time_range)

        # ── Step 2: KPI fingerprint 후보 생성/병합 ──
        await update_job(rd, job_id, progress_pct=40)
        await heartbeat(rd, job_key, job_id)

        # TODO: kpi_resolver.merge_candidates(org_id, logs)

        # ── Step 3: Driver 후보 필터링 + Scoring ──
        await update_job(rd, job_id, progress_pct=60)
        await heartbeat(rd, job_key, job_id)

        # TODO: driver_scorer.score(candidates, decay_model="step")

        # ── Step 4: Impact Graph 구성 ──
        await update_job(rd, job_id, progress_pct=80)
        await heartbeat(rd, job_key, job_id)

        # TODO: graph_builder.build(kpi_candidates, scored_drivers)
        graph = _build_placeholder_graph(org_id, kpi_fp, time_range, top, rd, job_id)

        # ── Step 5: Redis cache 저장 ──
        cache_key = (
            f"insight:{org_id}:impact:{kpi_fp}"
            f":{time_range}:{top}:2026-02-26.1"
        )
        await rd.set(cache_key, json.dumps(graph), ex=600)

        # ── Step 6: Job 완료 ──
        await finish_job(
            rd, job_id,
            status="done",
            ttl_s=JOB_TTL_DONE_S,
            progress_pct=100,
            result_url=(
                f"/api/insight/impact"
                f"?kpi_fingerprint={kpi_fp}"
                f"&time_range={time_range}"
                f"&top_drivers={top}"
            ),
        )

    except Exception as e:
        await finish_job(
            rd, job_id,
            status="failed",
            ttl_s=JOB_TTL_FAILED_S,
            progress_pct=100,
            error_code="INTERNAL_ERROR",
            error_message=str(e)[:500],
            poll_after_ms=3000,
        )


def _build_placeholder_graph(
    org_id: str, kpi_fp: str, time_range: str, top: int, rd, job_id: str,
) -> dict:
    """골격 그래프 — TODO: 실제 분석 로직으로 교체."""
    return {
        "meta": {
            "schema_version": "insight/v3",
            "analysis_version": "2026-02-26.1",
            "generated_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
            "time_range": {"from": "2026-01-27", "to": "2026-02-26"},
            "datasource": "unknown",
            "cache_hit": False,
            "limits": {
                "max_nodes": 120,
                "max_edges": 300,
                "depth": 3,
                "top_drivers": top,
            },
            "truncated": False,
            "explain": {
                "total_queries_analyzed": 0,
                "time_range_used": time_range,
                "mode": "primary",
                "decay_applied": False,
            },
        },
        "nodes": [],
        "edges": [],
        "paths": [],
    }
```

### PR6 체크리스트

- [x] Parse Worker: `pending` → `parsed` — regex 파서로 구현 (설계: sqlglot)
- [x] Parse Worker: `pending` → `fallback` — regex fallback 경로 구현
- [x] Parse Worker: `pending` → `failed` — 완전 실패 시 failed 전이
- [x] Parse Worker: `normalized_sql` NOT NULL 위반 없음
- [x] **✅ Parse Worker: `parse_mode`, `parse_confidence` 컬럼 UPDATE** — `parse_task.py:202-215` 확인 완료
- [x] Impact Worker: job 상태 `queued` → `running` → `done` 전이
- [x] Impact Worker: 실패 시 `failed` + `error` 저장 (필드명 설계: `error_message` → 구현: `error`)
- [x] **✅ Impact Worker: heartbeat로 TTL 연장** — Step 1.5/2/3/4 전환마다 `heartbeat()` 호출; jobmap TTL 동시 갱신
- [x] **✅ Impact Worker: graph 결과 별도 Redis cache 저장** — `_build_cache_key()` + `{"job_id":…,"result":…}` 포맷으로 저장 (C-2 fix)
- [x] **✅ Impact Worker: KpiMetricMapper 연결** — `load_kpi_definitions()` 호출 후 `analyze_query_logs(kpi_definitions=…)` 전달 (H-2 fix)
- [x] Impact Worker: progress 전이 — 10→15→20→50→80→100 (KPI 로드 step 추가)
- [ ] **⚠️ 파일 경로** — 설계: `worker/tasks/parse_task.py` → 구현: `worker/parse_task.py` (tasks 디렉토리 없음, 의도적)

---

## PR7: Impact Analysis Core

> **의존**: PR-6 (Workers)
> **파일**:
> - `services/weaver/app/services/query_log_analyzer.py`
> - `services/weaver/app/services/driver_scorer.py`
> - `services/weaver/app/services/impact_graph_builder.py`
> - `services/weaver/app/worker/tasks/impact_task.py` (수정 — placeholder → 실제 파이프라인)

### 7-1. query_log_analyzer.py

> **역할**: `insight_query_logs`에서 parsed JSON을 읽고 KPI 후보 컬럼 통계를 추출

```python
"""services/weaver/app/services/query_log_analyzer.py"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict, Counter
from datetime import datetime, timezone
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


# ── Dataclasses ──────────────────────────────────────────────

@dataclass
class AnalyzerConfig:
    max_queries: int = 50_000
    sample_rate: float = 1.0        # 1.0 = 전수, 0.5 = 50% 샘플
    max_candidate_columns: int = 500
    exclude_common_columns: frozenset = frozenset(
        {"id", "created_at", "updated_at", "deleted_at", "is_deleted"}
    )


@dataclass
class CandidateStats:
    appear: int = 0
    in_select: int = 0
    in_filter: int = 0
    in_group_by: int = 0
    join_degree: int = 0
    cooccur_with_kpi: int = 0
    distinct_tables: Set[str] = field(default_factory=set)
    distinct_queries: int = 0


@dataclass
class QueryEvidence:
    query_id: str
    datasource: str
    executed_at: str
    tables: list
    joins: list
    predicates: list
    select_cols: list
    group_by: list


@dataclass
class AnalysisResult:
    time_from: str
    time_to: str
    total_queries: int
    used_queries: int
    column_stats: Dict[str, CandidateStats]
    table_counts: Dict[str, int]
    join_edges: Dict[Tuple[str, str], int]
    evidence_samples: Dict[str, List[QueryEvidence]]


# ── Helpers ──────────────────────────────────────────────────

def _is_time_like(col_name: str) -> bool:
    low = col_name.lower()
    return any(
        kw in low
        for kw in ("date", "time", "timestamp", "created", "updated",
                    "modified", "_at", "_dt", "_ts")
    )


def _normalize_col_key(raw: str) -> str:
    """'schema.table.column' → 'table.column' (schema strip)"""
    parts = raw.strip().lower().split(".")
    if len(parts) >= 3:
        return f"{parts[-2]}.{parts[-1]}"
    if len(parts) == 2:
        return f"{parts[0]}.{parts[1]}"
    return ""


# ── Main Analysis ────────────────────────────────────────────

async def analyze_query_logs(
    session: AsyncSession,
    org_id: str,
    datasource: str,
    time_from_iso: str,
    time_to_iso: str,
    kpi_fingerprint: str,
    config: AnalyzerConfig = AnalyzerConfig(),
) -> AnalysisResult:
    """
    Read parsed query logs → aggregate column usage stats.

    Invariants:
      - RLS must be SET LOCAL before calling this function.
      - Only rows with parse_status IN ('primary','warn') are used.
    """

    # 1) Fetch parsed logs ─────────────────────────────────────
    query = text("""
        SELECT id, raw_sql, normalized_sql, datasource_id,
               executed_at, parsed_select, parsed_tables,
               parsed_joins, parsed_predicates, parsed_group_by,
               parse_status
        FROM insight_query_logs
        WHERE org_id      = :org_id
          AND datasource_id = :ds
          AND executed_at BETWEEN :t0 AND :t1
          AND parse_status IN ('primary', 'warn')
        ORDER BY executed_at DESC
        LIMIT :lim
    """)

    result = await session.execute(query, {
        "org_id": org_id,
        "ds": datasource,
        "t0": time_from_iso,
        "t1": time_to_iso,
        "lim": config.max_queries,
    })
    rows = result.fetchall()
    total = len(rows)

    # 2) Sample (if rate < 1.0) ────────────────────────────────
    if config.sample_rate < 1.0:
        import random
        k = max(1, int(total * config.sample_rate))
        used_rows = random.sample(rows, k)
    else:
        used_rows = rows

    # 3) Aggregate ─────────────────────────────────────────────
    column_stats: Dict[str, CandidateStats] = defaultdict(CandidateStats)
    table_counts: Dict[str, int] = Counter()
    join_edges: Dict[Tuple[str, str], int] = Counter()
    col_to_queries: Dict[str, Set[str]] = defaultdict(set)
    evidence_samples: Dict[str, List[QueryEvidence]] = defaultdict(list)

    kpi_lower = kpi_fingerprint.lower()
    time_from_iso_out = time_from_iso
    time_to_iso_out = time_to_iso

    for row in used_rows:
        query_id = str(row.id)
        ds = row.datasource_id or datasource
        executed_at = row.executed_at

        tables = row.parsed_tables or []
        joins = row.parsed_joins or []
        preds = row.parsed_predicates or []
        sel = row.parsed_select or []
        gb = row.parsed_group_by or []

        # Table counts
        for t in tables:
            tbl_name = (t.get("name") or "").lower()
            if tbl_name:
                table_counts[tbl_name] += 1

        # Join edges
        for j in joins:
            lt = (j.get("left_table") or "").lower()
            rt = (j.get("right_table") or "").lower()
            if lt and rt and lt != rt:
                key = tuple(sorted([lt, rt]))
                join_edges[key] += 1

        # KPI proxy detection
        has_kpi = any(
            kpi_lower in (s.get("expr", "") + s.get("alias", "")).lower()
            for s in sel
        )

        cols_in_query: Set[str] = set()

        # Select columns
        for s in sel:
            col_key = _normalize_col_key(s.get("expr", ""))
            if not col_key or "." not in col_key:
                continue
            t, c = col_key.split(".", 1)
            if c in config.exclude_common_columns:
                continue
            cs = column_stats[col_key]
            cs.appear += 1
            cs.in_select += 1
            cs.distinct_tables.add(t)
            col_to_queries[col_key].add(query_id)
            cols_in_query.add(col_key)

        # Filter columns
        for p in preds:
            col_key = _normalize_col_key(p.get("column", ""))
            if not col_key or "." not in col_key:
                continue
            t, c = col_key.split(".", 1)
            if c in config.exclude_common_columns:
                continue
            cs = column_stats[col_key]
            cs.appear += 1
            cs.in_filter += 1
            cs.distinct_tables.add(t)
            col_to_queries[col_key].add(query_id)
            cols_in_query.add(col_key)

        # Group-by columns
        for g in gb:
            col_key = _normalize_col_key(g if isinstance(g, str) else g.get("column", ""))
            if not col_key or "." not in col_key:
                continue
            t, c = col_key.split(".", 1)
            if c in config.exclude_common_columns:
                continue
            cs = column_stats[col_key]
            cs.appear += 1
            cs.in_group_by += 1
            cs.distinct_tables.add(t)
            col_to_queries[col_key].add(query_id)
            cols_in_query.add(col_key)

        # Join degree
        for j in joins:
            for side in ("left", "right"):
                col_key = _normalize_col_key(j.get(f"{side}_column") or "")
                if not col_key or "." not in col_key:
                    continue
                t, c = col_key.split(".", 1)
                if c in config.exclude_common_columns:
                    continue
                cs = column_stats[col_key]
                cs.appear += 1
                cs.join_degree += 1
                cs.distinct_tables.add(t)
                col_to_queries[col_key].add(query_id)
                cols_in_query.add(col_key)

        # KPI co-occurrence
        if has_kpi:
            for ck in cols_in_query:
                column_stats[ck].cooccur_with_kpi += 1

        # Evidence samples (bounded per column)
        ev = QueryEvidence(
            query_id=query_id,
            datasource=ds,
            executed_at=str(executed_at),
            tables=tables,
            joins=joins,
            predicates=preds,
            select_cols=sel,
            group_by=gb,
        )
        for ck in list(cols_in_query)[:50]:
            if len(evidence_samples[ck]) < 10:
                evidence_samples[ck].append(ev)

    # 4) Finalize distinct query counts ────────────────────────
    for ck, qs in col_to_queries.items():
        column_stats[ck].distinct_queries = len(qs)

    # 5) Hard cap candidates (keep most KPI-relevant) ──────────
    if len(column_stats) > config.max_candidate_columns:
        keys_sorted = sorted(
            column_stats.keys(),
            key=lambda k: column_stats[k].cooccur_with_kpi,
            reverse=True,
        )
        keep = set(keys_sorted[: config.max_candidate_columns])
        column_stats = {k: v for k, v in column_stats.items() if k in keep}
        evidence_samples = {k: v for k, v in evidence_samples.items() if k in keep}

    return AnalysisResult(
        time_from=time_from_iso_out,
        time_to=time_to_iso_out,
        total_queries=total,
        used_queries=len(used_rows),
        column_stats=dict(column_stats),
        table_counts=dict(table_counts),
        join_edges=dict(join_edges),
        evidence_samples=dict(evidence_samples),
    )
```

### 7-2. driver_scorer.py

> **역할**: 후보 컬럼을 DRIVER/DIMENSION으로 분류하고 스코어 산출
>
> **v1 스코어링 4축**:
> | 축 | 비중 | 설명 |
> |---|---|---|
> | **Usage** | 0.45 | KPI co-occur + distinct_queries breadth |
> | **Role Signal** | 0.25 | filter→DRIVER 가중, group_by→DIMENSION 가중 |
> | **Discriminative** | 0.20 | filter+join mix → DRIVER 가점, group_by only → DRIVER 감점 |
> | **Volatility** | 0.10 | 시간 2구간 분할, 등장 빈도 변화 큰 컬럼 가점 |
>
> **함정 방지**: 빈도만 쓰면 BI 대시보드 반복 쿼리에 오염 → 위 4축 혼합으로 최소한 방어

```python
"""services/weaver/app/services/driver_scorer.py"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math
from datetime import datetime, timezone

from .query_log_analyzer import AnalysisResult, CandidateStats, _is_time_like


@dataclass
class DriverScoreConfig:
    top_drivers: int = 20
    top_dimensions: int = 20
    w_usage: float = 0.45
    w_role: float = 0.25
    w_discriminative: float = 0.20
    w_volatility: float = 0.10
    time_dim_penalty: float = 0.35
    common_dim_penalty: float = 0.15
    min_distinct_queries: int = 2


@dataclass
class ScoredCandidate:
    column_key: str
    table: str
    column: str
    role: str          # "DRIVER" | "DIMENSION"
    score: float
    breakdown: dict


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))

def _log1p(x: float) -> float:
    return math.log(1.0 + max(0.0, x))

def _parse_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def score_candidates(
    analysis: AnalysisResult,
    kpi_fingerprint: str,
    cfg: DriverScoreConfig = DriverScoreConfig(),
) -> Tuple[List[ScoredCandidate], List[ScoredCandidate]]:
    """
    Returns (drivers_ranked, dimensions_ranked).
    """
    col_stats = analysis.column_stats
    if not col_stats:
        return [], []

    # ── Volatility: 2-halves split ────────────────────────────
    time_from = _parse_iso(analysis.time_from)
    time_to = _parse_iso(analysis.time_to)
    mid = time_from + (time_to - time_from) / 2

    vol_ratio: Dict[str, float] = {}
    for ck, evidences in analysis.evidence_samples.items():
        recent = older = 0
        for ev in evidences:
            try:
                dt = _parse_iso(ev.executed_at)
            except Exception:
                continue
            if dt >= mid:
                recent += 1
            else:
                older += 1
        vol_ratio[ck] = abs(math.log((recent + 1) / (older + 1)))

    drivers: List[ScoredCandidate] = []
    dims: List[ScoredCandidate] = []

    for ck, st in col_stats.items():
        if "." not in ck:
            continue
        table, col = ck.split(".", 1)

        if st.distinct_queries < cfg.min_distinct_queries:
            continue

        # ── Signals ───────────────────────────────────────────
        usage = _log1p(st.cooccur_with_kpi) * _sigmoid(st.distinct_queries / 3.0)

        total_role = max(1, st.in_filter + st.in_group_by + st.join_degree + st.in_select)
        filter_ratio = st.in_filter / total_role
        group_ratio = st.in_group_by / total_role
        join_ratio = st.join_degree / total_role

        discriminative_driver = _sigmoid(
            (filter_ratio + 0.6 * join_ratio) - 0.8 * group_ratio
        )
        discriminative_dim = _sigmoid(group_ratio - 0.5 * filter_ratio)

        volatility = _sigmoid(vol_ratio.get(ck, 0.0))

        # Penalties
        penalty = 0.0
        if _is_time_like(col):
            penalty += cfg.time_dim_penalty
        if col.lower() in ("status", "state", "type", "category", "region", "country"):
            penalty += cfg.common_dim_penalty

        # ── DRIVER score ──────────────────────────────────────
        role_driver = _sigmoid(
            2.0 * filter_ratio + 1.2 * join_ratio - 1.0 * group_ratio
        )
        score_driver = (
            cfg.w_usage * usage
            + cfg.w_role * role_driver
            + cfg.w_discriminative * discriminative_driver
            + cfg.w_volatility * volatility
        )
        score_driver = max(0.0, score_driver * (1.0 - penalty))

        drivers.append(ScoredCandidate(
            column_key=ck, table=table, column=col,
            role="DRIVER", score=float(score_driver),
            breakdown={
                "usage": float(usage),
                "filter_ratio": float(filter_ratio),
                "group_ratio": float(group_ratio),
                "join_ratio": float(join_ratio),
                "role_driver": float(role_driver),
                "discriminative": float(discriminative_driver),
                "volatility": float(volatility),
                "penalty": float(penalty),
                "cooccur_with_kpi": int(st.cooccur_with_kpi),
                "distinct_queries": int(st.distinct_queries),
            },
        ))

        # ── DIMENSION score ───────────────────────────────────
        role_dim = _sigmoid(
            2.2 * group_ratio + 0.4 * filter_ratio - 0.3 * join_ratio
        )
        score_dim = (
            cfg.w_usage * usage
            + cfg.w_role * role_dim
            + cfg.w_discriminative * discriminative_dim
            + 0.05 * volatility
        )
        dim_penalty = cfg.time_dim_penalty * 0.6 if _is_time_like(col) else 0.0
        score_dim = max(0.0, score_dim * (1.0 - dim_penalty))

        dims.append(ScoredCandidate(
            column_key=ck, table=table, column=col,
            role="DIMENSION", score=float(score_dim),
            breakdown={
                "usage": float(usage),
                "filter_ratio": float(filter_ratio),
                "group_ratio": float(group_ratio),
                "join_ratio": float(join_ratio),
                "role_dim": float(role_dim),
                "discriminative": float(discriminative_dim),
                "volatility": float(volatility),
                "penalty": float(dim_penalty),
                "cooccur_with_kpi": int(st.cooccur_with_kpi),
                "distinct_queries": int(st.distinct_queries),
            },
        ))

    drivers.sort(key=lambda x: x.score, reverse=True)
    dims.sort(key=lambda x: x.score, reverse=True)

    return drivers[: cfg.top_drivers], dims[: cfg.top_dimensions]
```

### 7-3. impact_graph_builder.py

> **역할**: 상위 DRIVER/DIMENSION을 받아 Impact Graph JSON(nodes/edges/paths) 생성
>
> **그래프 구성 규칙**:
> | 노드/엣지 | 소스 | 연결 조건 |
> |---|---|---|
> | KPI 노드 (root) | kpi_fingerprint | 항상 1개 |
> | DRIVER → KPI | score + cooccur_with_kpi | weight = 0.75·score + 0.25·(1-e^{-cooccur/5}) |
> | DRIVER ↔ DRIVER | join_edges (table co-usage) | join_strength > 0, weight > 0.15 |
> | DRIVER → DIMENSION | co-usage proxy (v1) | dim_score > 0.15, weight > 0.18 |
> | Top paths | KPI → A → B (depth ≤ 3) | sum(edge weights) descending |

```python
"""services/weaver/app/services/impact_graph_builder.py"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any
from collections import defaultdict
import math

from .query_log_analyzer import AnalysisResult
from .driver_scorer import ScoredCandidate


@dataclass
class GraphLimits:
    max_nodes: int = 120
    max_edges: int = 300
    depth: int = 3
    top_paths: int = 3


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _edge_weight(score: float, cooccur: int = 0) -> float:
    return _clamp(0.75 * score + 0.25 * (1.0 - math.exp(-cooccur / 5.0)))


def build_impact_graph(
    analysis: AnalysisResult,
    kpi_fingerprint: str,
    drivers: List[ScoredCandidate],
    dimensions: List[ScoredCandidate],
    limits: GraphLimits = GraphLimits(),
) -> Dict[str, Any]:
    """
    Returns:
      {
        "graph": { "meta":..., "nodes":[...], "edges":[...] },
        "paths": [ { "nodes":[...], "score":..., "why":... } ],
        "evidence": { "node_id": [ ...samples... ] }
      }
    """
    truncated = False
    kpi_id = f"kpi:{kpi_fingerprint}"

    # ── Nodes ─────────────────────────────────────────────────
    nodes: List[dict] = [{
        "id": kpi_id, "type": "KPI",
        "label": kpi_fingerprint, "score": 1.0,
        "meta": {"time_from": analysis.time_from, "time_to": analysis.time_to},
    }]

    def nid(c: ScoredCandidate) -> str:
        return f"col:{c.column_key}"

    max_drv = min(len(drivers), max(0, limits.max_nodes - 1))
    drv = drivers[:max_drv]
    remaining = limits.max_nodes - 1 - len(drv)
    dim = dimensions[: max(0, remaining)]

    for c in drv:
        nodes.append({
            "id": nid(c), "type": "DRIVER",
            "label": c.column_key, "score": float(c.score),
            "meta": c.breakdown,
        })
    for c in dim:
        nodes.append({
            "id": nid(c), "type": "DIMENSION",
            "label": c.column_key, "score": float(c.score),
            "meta": c.breakdown,
        })

    if len(nodes) >= limits.max_nodes:
        truncated = True

    node_scores = {n["id"]: float(n.get("score", 0.0)) for n in nodes}

    # ── Edges ─────────────────────────────────────────────────
    edges: List[dict] = []
    ec = 0

    # 1) KPI → DRIVER
    for c in drv:
        w = _edge_weight(c.score, c.breakdown.get("cooccur_with_kpi", 0))
        edges.append({
            "id": f"{kpi_id}__{nid(c)}", "source": kpi_id,
            "target": nid(c), "type": "INFLUENCES", "weight": w,
            "meta": {"reason": "cooccur_with_kpi+role_signal",
                     "cooccur_with_kpi": c.breakdown.get("cooccur_with_kpi", 0)},
        })
        ec += 1
        if ec >= limits.max_edges:
            truncated = True
            break

    # 2) DRIVER ↔ DRIVER (join table co-usage)
    driver_tables = {nid(c): c.table for c in drv}
    join_strength = defaultdict(int)
    for (ta, tb), cnt in analysis.join_edges.items():
        join_strength[tuple(sorted([ta, tb]))] += cnt

    if ec < limits.max_edges:
        drv_ids = [nid(c) for c in drv]
        for i in range(len(drv_ids)):
            for j in range(i + 1, len(drv_ids)):
                a, b = drv_ids[i], drv_ids[j]
                key = tuple(sorted([driver_tables[a], driver_tables[b]]))
                cnt = join_strength.get(key, 0)
                if cnt <= 0:
                    continue
                w = _clamp(
                    (1.0 - math.exp(-cnt / 6.0))
                    * (0.4 + 0.3 * node_scores[a] + 0.3 * node_scores[b])
                )
                if w < 0.15:
                    continue
                edges.append({
                    "id": f"{a}__{b}", "source": a, "target": b,
                    "type": "COUPLED", "weight": w,
                    "meta": {"reason": "join_edge", "join_count": cnt},
                })
                ec += 1
                if ec >= limits.max_edges:
                    truncated = True
                    break
            if ec >= limits.max_edges:
                break

    # 3) DRIVER → DIMENSION (co-usage proxy)
    if ec < limits.max_edges:
        drv_ids = [nid(c) for c in drv]
        dim_scores = {nid(c): c.score for c in dim}
        for d in drv_ids:
            for c in dim:
                m = nid(c)
                if dim_scores.get(m, 0) < 0.15:
                    continue
                w = _clamp(0.35 * node_scores[d] + 0.35 * node_scores[m])
                if w < 0.18:
                    continue
                edges.append({
                    "id": f"{d}__{m}", "source": d, "target": m,
                    "type": "EXPLAINS_BY", "weight": w,
                    "meta": {"reason": "co_usage_proxy"},
                })
                ec += 1
                if ec >= limits.max_edges:
                    truncated = True
                    break
            if ec >= limits.max_edges:
                break

    # ── Paths (top K, depth ≤ 3) ──────────────────────────────
    paths = _top_paths(kpi_id, edges, limits.top_paths)

    # ── Evidence (compact) ────────────────────────────────────
    evidence = _compact_evidence(analysis, [n["id"] for n in nodes])

    return {
        "graph": {
            "meta": {
                "schema_version": "insight/v3",
                "analysis_version": "v1",
                "generated_at": None,  # worker에서 채움
                "time_range": {"from": analysis.time_from, "to": analysis.time_to},
                "datasource": None,
                "cache_hit": False,
                "limits": {
                    "max_nodes": limits.max_nodes,
                    "max_edges": limits.max_edges,
                    "depth": limits.depth,
                    "top_paths": limits.top_paths,
                },
                "truncated": truncated,
                "explain": {
                    "total_queries_analyzed": analysis.total_queries,
                    "used_queries": analysis.used_queries,
                    "mode": "primary",
                },
            },
            "nodes": nodes,
            "edges": edges,
        },
        "paths": paths,
        "evidence": evidence,
    }


def _top_paths(root_id: str, edges: List[dict], k: int) -> List[dict]:
    """Simple path enumeration: root → A → B (depth ≤ 3)."""
    out_edges = defaultdict(list)
    for e in edges:
        out_edges[e["source"]].append(e)

    candidates = []
    for e1 in out_edges.get(root_id, []):
        a = e1["target"]
        candidates.append(([root_id, a], float(e1["weight"]), [e1["meta"]]))
        for e2 in out_edges.get(a, []):
            b = e2["target"]
            if b == root_id:
                continue
            score = float(e1["weight"]) + float(e2["weight"])
            candidates.append(([root_id, a, b], score, [e1["meta"], e2["meta"]]))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return [{"nodes": p, "score": s, "why": w} for p, s, w in candidates[:k]]


def _compact_evidence(
    analysis: AnalysisResult, node_ids: List[str],
) -> Dict[str, List[dict]]:
    """Per-node top 3 evidence for Query Subgraph."""
    out: Dict[str, List[dict]] = {}
    for nid in node_ids:
        if not nid.startswith("col:"):
            continue
        ck = nid.removeprefix("col:")
        evs = analysis.evidence_samples.get(ck, [])
        if not evs:
            continue
        out[nid] = [
            {
                "query_id": ev.query_id,
                "executed_at": ev.executed_at,
                "tables": ev.tables[:10],
                "joins": ev.joins[:6],
                "predicates": ev.predicates[:8],
                "group_by": ev.group_by[:8],
                "select": ev.select_cols[:8],
            }
            for ev in evs[:3]
        ]
    return out
```

### 7-4. impact_task.py 수정 — placeholder → 실제 파이프라인 연결

> PR6의 `_build_placeholder_graph` 를 실제 분석 파이프라인으로 교체

```python
# services/weaver/app/worker/tasks/impact_task.py  (PR7 수정 부분만)

from ...services.query_log_analyzer import analyze_query_logs, AnalyzerConfig
from ...services.driver_scorer import score_candidates, DriverScoreConfig
from ...services.impact_graph_builder import build_impact_graph, GraphLimits

# 기존 _build_placeholder_graph 함수를 아래로 교체:

async def _run_analysis(
    app, org_id: str, kpi_fp: str, payload: dict,
    rd, job_id: str, top: int,
) -> dict:
    """Actual impact analysis pipeline (replaces placeholder)."""
    from datetime import datetime, timedelta, timezone

    # time_range 문자열 → ISO 변환
    time_range = payload.get("time_range", "30d")
    now = datetime.now(timezone.utc)
    days = int(time_range.rstrip("d")) if time_range.endswith("d") else 30
    time_from = (now - timedelta(days=days)).isoformat()
    time_to = now.isoformat()

    async with app.state.session_factory() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.current_org_id', :org, true)"),
                {"org": org_id},
            )

            analysis = await analyze_query_logs(
                session=session,
                org_id=org_id,
                datasource=payload.get("datasource", "oracle"),
                time_from_iso=time_from,
                time_to_iso=time_to,
                kpi_fingerprint=kpi_fp,
                config=AnalyzerConfig(
                    max_queries=50_000,
                    sample_rate=1.0,
                ),
            )

    # Scoring (outside DB session — pure CPU)
    drivers, dims = score_candidates(
        analysis=analysis,
        kpi_fingerprint=kpi_fp,
        cfg=DriverScoreConfig(
            top_drivers=top,
            top_dimensions=20,
        ),
    )

    # Graph building (pure CPU)
    import time as _time
    graph_result = build_impact_graph(
        analysis=analysis,
        kpi_fingerprint=kpi_fp,
        drivers=drivers,
        dimensions=dims,
        limits=GraphLimits(max_nodes=120, max_edges=300, top_paths=3),
    )

    # Stamp generated_at
    graph_result["graph"]["meta"]["generated_at"] = _time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _time.gmtime()
    )
    graph_result["graph"]["meta"]["datasource"] = payload.get("datasource", "oracle")

    return graph_result
```

### PR7 체크리스트

- [x] `analyze_query_logs`: 50k rows 이내 정상 반환 — `max_queries` 설정 동작
- [ ] **⚠️ `analyze_query_logs`: parse_status 필터** — 설계: `IN ('primary','warn')` → 구현: `IN ('parsed','fallback')` (regex 파서에 맞게 변경)
- [x] `analyze_query_logs`: `sample_rate=0.5` → 약 절반 행만 분석 — 구현 동일
- [x] `score_candidates`: top 20 driver에 date/time 컬럼이 1위로 올라오지 않음 — `time_dim_penalty` 동작
- [x] `score_candidates`: KPI co-occur 0이면 score가 낮아짐 — 4축 스코어링 수식 100% 일치
- [x] `build_impact_graph`: nodes ≤ 120, edges ≤ 300 강제 — `GraphLimits` 동일
- [x] `build_impact_graph`: truncated=true 시 meta에 반영
- [x] `build_impact_graph`: paths 최대 3개, depth ≤ 3 — `_top_paths()` 구현 동일
- [x] placeholder → 실제 파이프라인 교체 — `impact_task.py`에서 analyzer→scorer→builder 파이프라인 연결 완료
- [x] RLS: 트랜잭션 내부에서만 DB 접근 — asyncpg `rls_session` 사용
- [ ] **⚠️ DB 접근 방식** — 설계: SQLAlchemy `AsyncSession` → 구현: asyncpg raw (의도적, 동작 동등)

---

## PR8: Accuracy Jump

> **의존**: PR-7 (Impact Analysis Core)
> **목적**: v1 → v1.5 정확도 도약 3축
>
> | 축 | 효과 | 복잡도 |
> |---|---|---|
> | Co-occur Matrix | DRIVER↔DRIVER, DRIVER→DIM 엣지가 실제 쿼리 동시 등장 기반 | O(cols_per_query²), 쿼리당 50개 제한 |
> | KPI ↔ Metric Mapping | 온톨로지 KPI가 실제 쿼리 metric과 정확히 연결 | 온톨로지 lookup 1회 |
> | Unified Node ID | Instance Graph와 Impact Graph 노드 ID 통합 → 탐색↔통찰 전환 | 컨벤션 변경 |
>
> **파일**:
> - `services/weaver/app/services/cooccur_matrix.py` (신규)
> - `services/weaver/app/services/kpi_metric_mapper.py` (신규)
> - `services/weaver/app/services/node_id.py` (신규)
> - `services/weaver/app/services/query_log_analyzer.py` (수정)
> - `services/weaver/app/services/impact_graph_builder.py` (수정)

### 8-1. cooccur_matrix.py — 쿼리 내 컬럼 동시 등장 행렬

> **핵심**: 같은 쿼리에서 함께 등장하는 컬럼 쌍의 빈도를 추적.
> DRIVER↔DRIVER 연결을 join_edges proxy 대신 **실측 동시 등장**으로 전환.
> DRIVER→DIMENSION도 동일하게 정확해짐.
>
> **비용 제어**: 쿼리당 컬럼 수를 `max_cols_per_query`(기본 50)로 cap → O(50²)=O(2500)/쿼리

```python
"""services/weaver/app/services/cooccur_matrix.py"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, List
from collections import Counter


@dataclass
class CooccurConfig:
    max_cols_per_query: int = 50
    min_cooccur_count: int = 2     # 2회 미만 동시 등장은 노이즈로 제거


@dataclass
class CooccurMatrix:
    """Symmetric co-occurrence counts between column keys."""
    pair_counts: Dict[Tuple[str, str], int] = field(default_factory=dict)
    total_queries: int = 0

    def strength(self, a: str, b: str) -> int:
        key = tuple(sorted([a, b]))
        return self.pair_counts.get(key, 0)

    def top_partners(self, col_key: str, k: int = 10) -> List[Tuple[str, int]]:
        """Return top-k co-occurring partners for a given column."""
        matches = []
        for (a, b), cnt in self.pair_counts.items():
            partner = None
            if a == col_key:
                partner = b
            elif b == col_key:
                partner = a
            if partner:
                matches.append((partner, cnt))
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:k]

    def normalize(self, a: str, b: str) -> float:
        """Jaccard-like normalization: cooccur(a,b) / (appear(a) + appear(b) - cooccur(a,b))."""
        cnt = self.strength(a, b)
        if cnt == 0:
            return 0.0
        # Use self-cooccur as proxy for appearance count
        a_total = self.strength(a, a) or cnt
        b_total = self.strength(b, b) or cnt
        denom = a_total + b_total - cnt
        return cnt / denom if denom > 0 else 0.0


def build_cooccur_matrix(
    per_query_columns: List[Set[str]],
    config: CooccurConfig = CooccurConfig(),
) -> CooccurMatrix:
    """
    Build co-occurrence matrix from per-query column sets.

    Args:
        per_query_columns: List of sets, each set contains column_keys
                           from one query (already capped at max_cols_per_query
                           by the caller).
    """
    pair_counter: Counter = Counter()
    total = 0

    for cols in per_query_columns:
        total += 1
        # Cap per query (defense in depth)
        col_list = sorted(cols)[: config.max_cols_per_query]

        # Self-counts (for normalization)
        for c in col_list:
            pair_counter[(c, c)] += 1

        # Pair counts
        for i in range(len(col_list)):
            for j in range(i + 1, len(col_list)):
                key = (col_list[i], col_list[j])  # already sorted
                pair_counter[key] += 1

    # Prune below threshold
    pruned = {
        k: v for k, v in pair_counter.items()
        if v >= config.min_cooccur_count or k[0] == k[1]  # keep self-counts
    }

    return CooccurMatrix(pair_counts=pruned, total_queries=total)
```

### 8-2. kpi_metric_mapper.py — 온톨로지 KPI ↔ 쿼리 metric 매핑

> **문제**: v1은 KPI fingerprint를 select.expr/alias substring으로만 매칭 → 오탐이 많음.
> **해결**: 온톨로지의 KPI 정의(metric SQL expression, alias 목록)를 로드하여 정확 매칭.
>
> **매칭 3단계**:
> 1. **Exact**: 온톨로지 KPI의 `metric_sql`이 쿼리 select expr에 정확히 포함
> 2. **Alias**: 온톨로지 KPI의 `aliases`가 쿼리 select alias에 매칭
> 3. **Fuzzy**: normalized 후 substring 매칭 (기존 v1 방식, 최후 수단)

```python
"""services/weaver/app/services/kpi_metric_mapper.py"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import re


@dataclass
class KpiDefinition:
    """Ontology KPI definition (loaded from ontology store)."""
    kpi_id: str
    name: str
    metric_sql: str                        # e.g. "SUM(order_amount)"
    aliases: List[str] = field(default_factory=list)  # e.g. ["total_sales", "매출합계"]
    table_hint: Optional[str] = None       # e.g. "orders"


@dataclass
class KpiMatch:
    kpi_id: str
    match_type: str   # "exact" | "alias" | "fuzzy"
    confidence: float  # 0.0 ~ 1.0
    matched_expr: str  # 매칭된 쿼리 표현식


@dataclass
class KpiMapperConfig:
    fuzzy_min_length: int = 4       # fuzzy는 4글자 이상만
    fuzzy_confidence: float = 0.3   # fuzzy 매칭 기본 confidence
    alias_confidence: float = 0.7
    exact_confidence: float = 1.0


def _normalize_sql_expr(expr: str) -> str:
    """Lowercase, strip whitespace, collapse spaces."""
    return re.sub(r"\s+", " ", expr.strip().lower())


class KpiMetricMapper:
    """Maps ontology KPI definitions to query select expressions."""

    def __init__(
        self,
        kpi_definitions: List[KpiDefinition],
        config: KpiMapperConfig = KpiMapperConfig(),
    ):
        self.definitions = kpi_definitions
        self.config = config
        # Pre-compute normalized forms
        self._norm_metrics: Dict[str, KpiDefinition] = {}
        self._alias_map: Dict[str, KpiDefinition] = {}
        for kd in kpi_definitions:
            norm = _normalize_sql_expr(kd.metric_sql)
            self._norm_metrics[norm] = kd
            for alias in kd.aliases:
                self._alias_map[alias.lower().strip()] = kd

    def match_select_exprs(
        self,
        select_exprs: List[dict],
    ) -> List[KpiMatch]:
        """
        Match query SELECT expressions against ontology KPIs.

        Args:
            select_exprs: [{"expr": "SUM(o.amount)", "alias": "total_sales"}, ...]

        Returns:
            List of KpiMatch (may be empty if no KPI found).
        """
        matches: List[KpiMatch] = []
        seen_kpis: Set[str] = set()

        for sel in select_exprs:
            expr = sel.get("expr", "")
            alias = sel.get("alias", "")
            norm_expr = _normalize_sql_expr(expr)
            norm_alias = alias.lower().strip()

            # 1) Exact metric SQL match
            for norm_metric, kd in self._norm_metrics.items():
                if norm_metric in norm_expr or norm_expr in norm_metric:
                    if kd.kpi_id not in seen_kpis:
                        matches.append(KpiMatch(
                            kpi_id=kd.kpi_id,
                            match_type="exact",
                            confidence=self.config.exact_confidence,
                            matched_expr=expr,
                        ))
                        seen_kpis.add(kd.kpi_id)

            # 2) Alias match
            if norm_alias and norm_alias in self._alias_map:
                kd = self._alias_map[norm_alias]
                if kd.kpi_id not in seen_kpis:
                    matches.append(KpiMatch(
                        kpi_id=kd.kpi_id,
                        match_type="alias",
                        confidence=self.config.alias_confidence,
                        matched_expr=alias,
                    ))
                    seen_kpis.add(kd.kpi_id)

            # 3) Fuzzy (substring in expr or alias)
            for kd in self.definitions:
                if kd.kpi_id in seen_kpis:
                    continue
                kpi_name_lower = kd.name.lower()
                if len(kpi_name_lower) < self.config.fuzzy_min_length:
                    continue
                if kpi_name_lower in norm_expr or kpi_name_lower in norm_alias:
                    matches.append(KpiMatch(
                        kpi_id=kd.kpi_id,
                        match_type="fuzzy",
                        confidence=self.config.fuzzy_confidence,
                        matched_expr=expr or alias,
                    ))
                    seen_kpis.add(kd.kpi_id)

        return matches

    def best_match(
        self,
        select_exprs: List[dict],
    ) -> Optional[KpiMatch]:
        """Return highest-confidence match, or None."""
        matches = self.match_select_exprs(select_exprs)
        if not matches:
            return None
        return max(matches, key=lambda m: m.confidence)


async def load_kpi_definitions(session, org_id: str) -> List[KpiDefinition]:
    """
    Load KPI definitions from ontology store.

    Expected table: ontology_kpis (or equivalent)
    Columns: kpi_id, name, metric_sql, aliases (JSONB), table_hint
    """
    from sqlalchemy import text

    result = await session.execute(
        text("""
            SELECT kpi_id, name, metric_sql,
                   COALESCE(aliases, '[]'::jsonb) AS aliases,
                   table_hint
            FROM ontology_kpis
            WHERE org_id = :org_id AND is_active = true
        """),
        {"org_id": org_id},
    )
    rows = result.fetchall()
    return [
        KpiDefinition(
            kpi_id=r.kpi_id,
            name=r.name,
            metric_sql=r.metric_sql,
            aliases=r.aliases if isinstance(r.aliases, list) else [],
            table_hint=r.table_hint,
        )
        for r in rows
    ]
```

### 8-3. node_id.py — Instance Graph / Impact Graph 통합 노드 ID 컨벤션

> **문제**: Instance Graph(스키마 기반)와 Impact Graph(쿼리 기반)가 별도 노드 ID → 프론트에서 "탐색↔통찰" 전환 불가.
> **해결**: 통합 노드 ID 규칙을 정의하고, 양쪽 그래프 빌더가 동일 함수를 사용.
>
> **통합 규칙**:
> | 타입 | 패턴 | 예시 |
> |---|---|---|
> | Table | `tbl:{schema}.{table}` | `tbl:public.orders` |
> | Column | `col:{schema}.{table}.{column}` | `col:public.orders.amount` |
> | KPI | `kpi:{kpi_id}` | `kpi:total_revenue` |
> | Metric (raw) | `metric:{fingerprint}` | `metric:sum_order_amount` |
> | Datasource | `ds:{datasource_id}` | `ds:oracle_prod` |

```python
"""services/weaver/app/services/node_id.py"""
from __future__ import annotations

import re
from typing import Optional


# ── Node ID prefixes ─────────────────────────────────────────
PREFIX_TABLE = "tbl"
PREFIX_COLUMN = "col"
PREFIX_KPI = "kpi"
PREFIX_METRIC = "metric"
PREFIX_DATASOURCE = "ds"

_VALID_PREFIXES = frozenset({
    PREFIX_TABLE, PREFIX_COLUMN, PREFIX_KPI,
    PREFIX_METRIC, PREFIX_DATASOURCE,
})


def table_node_id(schema: str, table: str) -> str:
    """tbl:{schema}.{table}"""
    return f"{PREFIX_TABLE}:{_norm(schema)}.{_norm(table)}"


def column_node_id(schema: str, table: str, column: str) -> str:
    """col:{schema}.{table}.{column}"""
    return f"{PREFIX_COLUMN}:{_norm(schema)}.{_norm(table)}.{_norm(column)}"


def column_node_id_from_key(column_key: str, schema: str = "public") -> str:
    """
    Convert legacy 'table.column' key → unified 'col:schema.table.column'.
    For backward compat with query_log_analyzer output.
    """
    parts = column_key.lower().split(".")
    if len(parts) == 2:
        return f"{PREFIX_COLUMN}:{_norm(schema)}.{parts[0]}.{parts[1]}"
    if len(parts) >= 3:
        return f"{PREFIX_COLUMN}:{parts[0]}.{parts[1]}.{parts[2]}"
    return f"{PREFIX_COLUMN}:{_norm(schema)}.unknown.{column_key.lower()}"


def kpi_node_id(kpi_id: str) -> str:
    """kpi:{kpi_id}"""
    return f"{PREFIX_KPI}:{_norm(kpi_id)}"


def metric_node_id(fingerprint: str) -> str:
    """metric:{fingerprint}"""
    return f"{PREFIX_METRIC}:{_norm(fingerprint)}"


def datasource_node_id(datasource_id: str) -> str:
    """ds:{datasource_id}"""
    return f"{PREFIX_DATASOURCE}:{_norm(datasource_id)}"


def parse_node_id(node_id: str) -> Optional[dict]:
    """
    Parse a unified node ID back into components.

    Returns:
        {"prefix": "col", "parts": ["public", "orders", "amount"]}
        or None if invalid.
    """
    if ":" not in node_id:
        return None
    prefix, rest = node_id.split(":", 1)
    if prefix not in _VALID_PREFIXES:
        return None
    return {"prefix": prefix, "parts": rest.split(".")}


def is_same_entity(id_a: str, id_b: str) -> bool:
    """
    Check if two node IDs refer to the same logical entity.
    Handles schema defaulting (e.g., 'col:orders.amount' == 'col:public.orders.amount').
    """
    pa = parse_node_id(id_a)
    pb = parse_node_id(id_b)
    if not pa or not pb:
        return False
    if pa["prefix"] != pb["prefix"]:
        return False
    # Normalize: if one has 2 parts and other has 3, prepend 'public'
    a_parts = pa["parts"]
    b_parts = pb["parts"]
    if pa["prefix"] == PREFIX_COLUMN:
        if len(a_parts) == 2:
            a_parts = ["public"] + a_parts
        if len(b_parts) == 2:
            b_parts = ["public"] + b_parts
    elif pa["prefix"] == PREFIX_TABLE:
        if len(a_parts) == 1:
            a_parts = ["public"] + a_parts
        if len(b_parts) == 1:
            b_parts = ["public"] + b_parts
    return a_parts == b_parts


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9_.:-]", "", s.lower().strip())
```

### 8-4. query_log_analyzer.py 수정 — co-occur 수집 통합

> analyzer가 분석 루프 내에서 per-query column set을 수집, `CooccurMatrix`를 `AnalysisResult`에 포함

```python
# services/weaver/app/services/query_log_analyzer.py  (PR8 수정 부분)

# ── 추가 import ──────────────────────────────────────────────
from .cooccur_matrix import build_cooccur_matrix, CooccurConfig, CooccurMatrix

# ── AnalysisResult 확장 ──────────────────────────────────────
@dataclass
class AnalysisResult:
    time_from: str
    time_to: str
    total_queries: int
    used_queries: int
    column_stats: Dict[str, CandidateStats]
    table_counts: Dict[str, int]
    join_edges: Dict[Tuple[str, str], int]
    evidence_samples: Dict[str, List[QueryEvidence]]
    cooccur: Optional[CooccurMatrix] = None  # PR8 추가


# ── analyze_query_logs 수정 (루프 끝에 추가) ─────────────────

    # 기존 루프 내부에서 이미 cols_in_query를 수집하고 있음.
    # PR8: per_query_columns 리스트도 함께 수집.

    per_query_columns: List[Set[str]] = []  # 루프 전에 선언

    # ... (기존 for row in used_rows 루프 내부, 마지막에)
        per_query_columns.append(cols_in_query.copy())

    # ... (기존 finalize 후, return 전에)
    cooccur = build_cooccur_matrix(
        per_query_columns=per_query_columns,
        config=CooccurConfig(max_cols_per_query=50, min_cooccur_count=2),
    )

    return AnalysisResult(
        # ... (기존 필드 동일)
        cooccur=cooccur,  # PR8 추가
    )
```

### 8-5. impact_graph_builder.py 수정 — co-occur 기반 엣지 + unified node ID

> DRIVER↔DRIVER: join_edges proxy → **실제 co-occur strength** 사용
> DRIVER→DIMENSION: score proxy → **co-occur strength** 사용
> 모든 node ID: `node_id.py`의 통합 함수 사용

```python
# services/weaver/app/services/impact_graph_builder.py  (PR8 수정 부분)

# ── 추가 import ──────────────────────────────────────────────
from .node_id import (
    kpi_node_id, column_node_id_from_key,
    table_node_id, parse_node_id,
)
from .cooccur_matrix import CooccurMatrix

# ── build_impact_graph 수정 ──────────────────────────────────

def build_impact_graph(
    analysis: AnalysisResult,
    kpi_fingerprint: str,
    drivers: List[ScoredCandidate],
    dimensions: List[ScoredCandidate],
    limits: GraphLimits = GraphLimits(),
    schema: str = "public",          # PR8: default schema for node ID
) -> Dict[str, Any]:

    truncated = False
    kpi_id = kpi_node_id(kpi_fingerprint)  # PR8: unified

    # Nodes
    nodes: List[dict] = [{
        "id": kpi_id, "type": "KPI",
        "label": kpi_fingerprint, "score": 1.0,
        "meta": {"time_from": analysis.time_from, "time_to": analysis.time_to},
    }]

    def nid(c: ScoredCandidate) -> str:
        return column_node_id_from_key(c.column_key, schema)  # PR8: unified

    # ... (노드 추가 로직은 동일)

    # ── Edges: PR8에서 co-occur 사용 ──────────────────────────
    cooccur = analysis.cooccur  # may be None (PR7 호환)

    # 2) DRIVER ↔ DRIVER — co-occur 기반 (PR8)
    if cooccur and ec < limits.max_edges:
        drv_ids = [nid(c) for c in drv]
        drv_keys = {nid(c): c.column_key for c in drv}
        for i in range(len(drv_ids)):
            for j in range(i + 1, len(drv_ids)):
                a, b = drv_ids[i], drv_ids[j]
                cnt = cooccur.strength(drv_keys[a], drv_keys[b])
                if cnt < 2:
                    continue
                norm_strength = cooccur.normalize(drv_keys[a], drv_keys[b])
                w = _clamp(
                    0.5 * norm_strength
                    + 0.25 * node_scores.get(a, 0)
                    + 0.25 * node_scores.get(b, 0)
                )
                if w < 0.12:
                    continue
                edges.append({
                    "id": f"{a}__{b}", "source": a, "target": b,
                    "type": "COUPLED", "weight": w,
                    "meta": {
                        "reason": "cooccur_matrix",
                        "cooccur_count": cnt,
                        "cooccur_norm": round(norm_strength, 4),
                    },
                })
                ec += 1
                if ec >= limits.max_edges:
                    truncated = True
                    break
            if ec >= limits.max_edges:
                break

    # 3) DRIVER → DIMENSION — co-occur 기반 (PR8)
    if cooccur and ec < limits.max_edges:
        drv_keys = {nid(c): c.column_key for c in drv}
        dim_keys = {nid(c): c.column_key for c in dim}
        for d_nid, d_key in drv_keys.items():
            for m_nid, m_key in dim_keys.items():
                cnt = cooccur.strength(d_key, m_key)
                if cnt < 2:
                    continue
                norm_strength = cooccur.normalize(d_key, m_key)
                w = _clamp(
                    0.5 * norm_strength
                    + 0.3 * node_scores.get(d_nid, 0)
                    + 0.2 * node_scores.get(m_nid, 0)
                )
                if w < 0.15:
                    continue
                edges.append({
                    "id": f"{d_nid}__{m_nid}", "source": d_nid, "target": m_nid,
                    "type": "EXPLAINS_BY", "weight": w,
                    "meta": {
                        "reason": "cooccur_matrix",
                        "cooccur_count": cnt,
                        "cooccur_norm": round(norm_strength, 4),
                    },
                })
                ec += 1
                if ec >= limits.max_edges:
                    truncated = True
                    break
            if ec >= limits.max_edges:
                break

    # ... (paths, evidence, return 동일)
```

### PR8 체크리스트

**개별 모듈 (구현 완료):**

- [x] `CooccurMatrix.strength(a,b)` == `CooccurMatrix.strength(b,a)` (대칭성) — `tuple(sorted(...))` 구현
- [x] `CooccurMatrix`: min_cooccur_count=2 미만 pair 제거 — pruning 구현
- [x] `KpiMetricMapper`: exact=1.0, alias=0.7, fuzzy=0.3 — 3단계 매칭 구현
- [x] `KpiMetricMapper`: KPI 없으면 빈 리스트 반환
- [x] `node_id`: `col:orders.amount` == `col:public.orders.amount` — `is_same_entity()` 구현
- [x] `node_id`: parse_node_id → round-trip 성공

**통합 (구현 완료 — 2026-02-27 기준):**

- [x] **✅ `load_kpi_definitions`: DB 로더 함수** — `asyncpg`로 `weaver.ontology_kpi_definitions` 조회, 테이블 미존재 시 빈 리스트 반환 (`kpi_metric_mapper.py:145-194`)
- [x] **✅ `query_log_analyzer.py` 수정: per_query_columns 수집 + cooccur 빌드** — `AnalysisResult.cooccur` 필드 추가, 루프에서 `per_query_columns` 수집, `build_cooccur_matrix()` 호출
- [x] **✅ `impact_graph_builder.py` 수정: cooccur 기반 엣지** — `cooccur.strength()` 우선 사용, 없을 때 `join_edges` fallback; COUPLED·EXPLAINS_BY 엣지 모두 적용
- [x] **✅ `impact_graph_builder.py` 수정: unified node_id** — `kpi_node_id()`, `column_node_id_from_key()` 사용 (`node_id.py` import), 인라인 f-string 제거
- [x] **✅ `build_impact_graph`: COUPLED 엣지 `meta.reason == "cooccur_matrix"`** — `impact_graph_builder.py` line 165 수정 완료
- [x] **✅ Query Subgraph 빌더 `node_id.py` 적용** — `_parse_result_to_graph()`: `table_node_id()` + `column_node_id()` 적용, `tbl_coords` 역매핑 + `seen_node_ids` 중복 방지 추가

---

## main.py 부트스트랩

> **파일**: `services/weaver/app/main.py`

```python
from fastapi import FastAPI

from .api.insight import router as insight_router
from .core.error_handler import insight_error_handler
from .core.errors import InsightError
from .core.trace_middleware import TraceIdMiddleware
from .core.redis_client import create_redis


def create_app(settings) -> FastAPI:
    app = FastAPI(title="Weaver Insight API", version="3.2.1")
    app.state.debug = settings.DEBUG

    # ── 미들웨어 ──
    app.add_middleware(TraceIdMiddleware)

    # ── 에러 핸들러 ──
    app.add_exception_handler(InsightError, insight_error_handler)

    # ── DB session factory ──
    app.state.session_factory = settings.SESSION_FACTORY

    # ── Redis ──
    app.state.redis = create_redis(settings.REDIS_URL)

    # ── Job Queue (추상 — 실제 구현체 주입) ──
    app.state.job_queue = settings.JOB_QUEUE

    # ── Routers ──
    app.include_router(insight_router)

    return app
```

---

## 실전 위험 포인트

> "이대로 붙이면 바로 터지는 포인트" 10개와 방지책.

| # | 위험 | 증상 | 방지책 | 구현 상태 |
|---|---|---|---|---|
| 1 | **SET LOCAL 적용 전 쿼리 실행** | 다른 tenant 데이터 접근 | `rls_session` 컨텍스트에서만 DB 접근 | ✅ 해결 — `rls_session(pool, tenant_id)` 구현 |
| 2 | **insert_logs의 exists 체크 + insert 레이스** | 중복 INSERT 가능 | `UNIQUE` + `ON CONFLICT DO NOTHING` | ✅ 해결 — DDL에 UNIQUE, 구현에 ON CONFLICT 적용 |
| 3 | **job 생성 경쟁 조건** | 중복 job 생성 | `SET NX` 사용 + 실패 시 기존값 재조회 | ✅ 해결 — `rd.set(map_key, job_id, nx=True, ex=TTL_RUNNING)` 원자적 생성 (H-1 fix) |
| 4 | **impact API cache_hit meta 미업데이트** | 프론트 상태바 오동작 | cached 값 파싱 후 반환 | ✅ 해결 — cache-first 조회 + `graph["meta"]["cache_hit"] = True` 세팅 (C-2 fix) |
| 5 | **parse를 normalized_sql로만 수행** | 원문 기반 정보 부족 | 우선 OK, 향후 `sql_raw_enc` 복호화 추가 | ✅ 수용 — Phase 2 |
| 6 | **`/impact`에서 tenant_id를 헤더에서 직접 추출** | 보안 우회 | `Depends(get_effective_tenant_id)` 통일 | ✅ 해결 — 모든 엔드포인트에 auth 적용 |
| 7 | **KPI fingerprint 매칭이 허술** | 엉뚱한 KPI로 그래프 생성 | PR8 KpiMetricMapper 정확 매칭 | ✅ 해소 — `load_kpi_definitions` 구현, KpiMetricMapper 3-tier 매칭 동작 |
| 8 | **DRIVER↔DRIVER co-occur를 join proxy로만 연결** | 같은 테이블 내 컬럼 연결 누락 | PR8 CooccurMatrix 기반 엣지 | ✅ 해소 — `cooccur.strength()` 우선 사용, join_edges fallback 포함 |
| 9 | **그래프 노드/엣지 과다 → UI 프리즈** | 브라우저 렌더링 지연 | `GraphLimits` 강제 + `truncated` | ✅ 해결 — max_nodes=120, max_edges=300 동작 |
| 10 | **Instance↔Impact 노드 ID 불일치** | 탐색↔통찰 전환 불가 | `node_id.py` 통합 컨벤션 | ✅ 해소 — Impact Graph + Query Subgraph 빌더 모두 `tbl:{schema}.{table}` / `col:{schema}.{table}.{column}` 형식 통일 |

### 레이스 조건 방어 강화 (권장)

```sql
-- PR1 DDL에 추가 권장: query_id 중복 방어
ALTER TABLE insight_query_logs
    ADD CONSTRAINT uq_iql_org_query_id UNIQUE (org_id, query_id);
```

```python
# insert_logs에서 ON CONFLICT 활용
await session.execute(
    text("""
    INSERT INTO insight_query_logs (...) VALUES (...)
    ON CONFLICT (org_id, query_id) DO NOTHING
    RETURNING id
    """),
    params,
)
# RETURNING id가 NULL이면 deduped += 1
```

---

## 파일 트리 요약

> **범례**: 설계 경로 → 실제 경로 (괄호 안은 변경 사유)

```text
설계 경로                                        실제 구현 경로                                       상태
─────────────────────────────────────────────── ─────────────────────────────────────────────────── ────
alembic/versions/20260226_01_insight_tables.py → services/weaver/app/services/insight_store.py       ✅ (idempotent DDL로 전환)
app/core/errors.py + error_handler.py          → app/core/insight_errors.py                          ✅ (단일 파일 통합)
app/core/rls_session.py                        → app/core/rls_session.py                             ✅ (asyncpg 전환)
app/core/trace_middleware.py                   → main.py request_context_middleware                   ✅ (기존 미들웨어 활용)
app/core/authz.py                              → app/core/insight_auth.py                            ✅
app/api/insight.py                             → app/api/insight.py                                  ✅
app/api/schemas/insight_logs.py                → app/api/schemas/insight_schemas.py                  ✅
app/core/sql_normalize.py                      → app/services/sql_normalize.py                       ⚠️ (PII regex 누락)
app/services/idempotency.py                    → app/services/idempotency.py                         ⚠️ (hash 절단 누락)
app/services/query_log_store.py                → app/services/insight_query_store.py                 ⚠️ (MAX_SQL_LENGTH 누락)
app/core/redis_client.py                       → app/core/insight_redis.py                           ✅
app/services/job_store.py                      → app/services/insight_job_store.py                   ⚠️ (heartbeat·TTL분리 누락)
app/core/sql_parser.py                         → (미생성 — regex 파서가 parse_task에 내장)            ⚠️ (의도적 변경)
app/worker/tasks/parse_task.py                 → app/worker/parse_task.py                            ✅ (tasks 디렉토리 생략)
app/worker/tasks/impact_task.py                → app/worker/impact_task.py                           ⚠️ (heartbeat·cache 누락)
app/services/query_log_analyzer.py             → app/services/query_log_analyzer.py                  ✅ (PR8 cooccur 통합 완료)
app/services/driver_scorer.py                  → app/services/driver_scorer.py                       ✅ (수식 100% 일치)
app/services/impact_graph_builder.py           → app/services/impact_graph_builder.py                ✅ (PR8 cooccur·node_id 통합 완료)
app/services/cooccur_matrix.py                 → app/services/cooccur_matrix.py                      ✅ (모듈 완성 + graph_builder 통합)
app/services/kpi_metric_mapper.py              → app/services/kpi_metric_mapper.py                   ✅ (load_kpi_definitions 구현 완료)
app/services/node_id.py                        → app/services/node_id.py                             ✅ (모듈 완성 + graph_builder 통합)
app/api/insight.py (_parse_result_to_graph)    → app/api/insight.py                                  ✅ (node_id.py 적용 완료 — table_node_id + column_node_id)
app/services/partition_manager.py              → (미생성 — PARTITION 미사용)                          ✅ (의도적 생략)
main.py                                        → app/main.py                                         ✅
```

---

## v1 정확도 한계와 v2 진화 경로

> PR7/PR8 이후 가장 가치가 큰 정확도 점프 방향 3가지.

| # | 개선 | 현재 (v1/v1.5) | 목표 (v2) | 예상 효과 |
|---|---|---|---|---|
| 1 | **Per-query co-occur matrix 정밀화** | evidence_samples 10개 한정, 2-halves volatility | full matrix + time-window sliding | DRIVER↔DRIVER 엣지 정확도 2~3x |
| 2 | **KPI ↔ metric 온톨로지 deep binding** | substring/alias 매칭 (PR8) | metric SQL AST 비교 + 온톨로지 계층 traversal | KPI 오탐률 < 5% |
| 3 | **Instance Graph + Impact Graph 자동 병합** | 같은 node_id 규칙 (PR8) | 프론트에서 토글 시 자동 overlay, 양방향 하이라이트 | 탐색↔통찰 UX 완성 |
