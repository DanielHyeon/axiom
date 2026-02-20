# ETL 파이프라인

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **Phase**: 3.6
> **근거**: 01_architecture/olap-engine.md, ADR-003

---

## 이 문서가 답하는 질문

- OLTP 데이터를 OLAP Materialized View로 어떻게 동기화하는가?
- Full Sync와 Incremental Sync의 차이와 사용 시점은?
- Airflow DAG는 어떻게 구성되는가?
- MV REFRESH 중 서비스 가용성은 어떻게 보장하는가?

---

## 1. ETL 아키텍처

```
┌─ OLTP (Axiom Core) ──────────────────────────────────────────┐
│  cases, stakeholders, performance_records, assets,              │
│  cash_flow_entries, case_user_roles                             │
└───────────────────┬───────────────────────────────────────────┘
                    │
        ┌───────────┤──────────────┐
        │           │              │
        ▼           ▼              ▼
   Full Sync   Incremental    Event-Driven
   (Airflow)   (API 트리거)   (Outbox 이벤트)
        │           │              │
        └───────────┤──────────────┘
                    │
                    ▼
┌─ OLAP (Materialized Views) ──────────────────────────────────┐
│  mv_business_fact, mv_cashflow_fact                            │
│  dim_case_type, dim_org, dim_time, dim_stakeholder_type        │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. 동기화 전략

### 2.1 Full Sync

**목적**: 전체 데이터를 재집계하여 MV를 완전히 갱신한다.

```sql
-- Materialized View 전체 갱신
-- CONCURRENTLY: 읽기 차단 없이 갱신 (unique index 필요)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_business_fact;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_cashflow_fact;
```

| 항목 | 값 |
|------|-----|
| **실행 시점** | 매일 03:00 UTC (Airflow DAG) |
| **소요 시간** | 30초 ~ 5분 (데이터 규모 의존) |
| **읽기 차단** | 없음 (CONCURRENTLY) |
| **재시도** | 3회, 5분 간격 |
| **실패 알림** | Slack + 이메일 |

### 2.2 Incremental Sync

**목적**: 변경된 데이터만 반영한다. Full Sync 사이의 갱신용.

```python
async def incremental_sync(
    target_view: str,
    since: datetime | None = None
) -> SyncResult:
    """
    Incremental sync by tracking changes since last sync.

    For Materialized Views, PostgreSQL doesn't support true incremental
    refresh. We use CONCURRENTLY refresh but limit frequency to avoid
    contention.
    """
    # Check if enough time has passed since last refresh
    last_refresh = await get_last_refresh_time(target_view)
    if last_refresh and (datetime.utcnow() - last_refresh).seconds < 300:
        return SyncResult(status="skipped", reason="Too recent")

    # Acquire advisory lock to prevent concurrent refresh
    lock_acquired = await try_advisory_lock(target_view)
    if not lock_acquired:
        return SyncResult(status="skipped", reason="Another sync in progress")

    try:
        start = time.monotonic()
        await execute_refresh(target_view)
        elapsed = time.monotonic() - start

        await record_sync_history(target_view, elapsed)
        return SyncResult(status="completed", duration_seconds=elapsed)
    finally:
        await release_advisory_lock(target_view)
```

### 2.3 Event-Driven Sync

**목적**: 특정 이벤트 발생 시 즉시 관련 MV를 갱신한다.

```python
# Event triggers from Axiom Core's event_outbox
EVENT_TO_VIEW_MAP = {
    "case_created": ["mv_business_fact"],
    "case_status_changed": ["mv_business_fact"],
    "stakeholder_registered": ["mv_business_fact"],
    "stakeholder_admitted": ["mv_business_fact"],
    "performance_recorded": ["mv_business_fact", "mv_cashflow_fact"],
    "cash_flow_entry_created": ["mv_cashflow_fact"],
}

async def handle_outbox_event(event: OutboxEvent):
    """
    Triggered by Redis Streams consumer.
    Debounces rapid events (waits 10 seconds for batch).
    """
    target_views = EVENT_TO_VIEW_MAP.get(event.event_type, [])
    for view in target_views:
        await enqueue_refresh(view, debounce_seconds=10)
```

---

## 3. Airflow DAG 설계

### 3.1 DAG 정의

```python
from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'axiom-vision',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': True,
    'email': ['ops@axipient.com'],
}

dag = DAG(
    'vision_olap_full_sync',
    default_args=default_args,
    description='Daily full sync of OLAP Materialized Views',
    schedule_interval='0 3 * * *',  # Daily at 03:00 UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['vision', 'olap', 'etl'],
)

# Task 1: Validate source data
validate_source = PythonOperator(
    task_id='validate_source_data',
    python_callable=validate_source_tables,
    dag=dag,
)

# Task 2: Refresh dimension tables first
refresh_dim_case_type = PostgresOperator(
    task_id='refresh_dim_case_type',
    postgres_conn_id='axiom_postgres',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY dim_case_type;',
    dag=dag,
)

refresh_dim_org = PostgresOperator(
    task_id='refresh_dim_org',
    postgres_conn_id='axiom_postgres',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY dim_org;',
    dag=dag,
)

refresh_dim_time = PostgresOperator(
    task_id='refresh_dim_time',
    postgres_conn_id='axiom_postgres',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY dim_time;',
    dag=dag,
)

refresh_dim_stakeholder = PostgresOperator(
    task_id='refresh_dim_stakeholder',
    postgres_conn_id='axiom_postgres',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY dim_stakeholder_type;',
    dag=dag,
)

# Task 3: Refresh fact tables (after dimensions)
refresh_business_fact = PostgresOperator(
    task_id='refresh_business_fact',
    postgres_conn_id='axiom_postgres',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY mv_business_fact;',
    dag=dag,
)

refresh_cashflow_fact = PostgresOperator(
    task_id='refresh_cashflow_fact',
    postgres_conn_id='axiom_postgres',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY mv_cashflow_fact;',
    dag=dag,
)

# Task 4: Invalidate Redis cache
invalidate_cache = PythonOperator(
    task_id='invalidate_redis_cache',
    python_callable=invalidate_olap_cache,
    dag=dag,
)

# Task 5: Record sync completion
record_sync = PythonOperator(
    task_id='record_sync_completion',
    python_callable=record_sync_metadata,
    dag=dag,
)

# DAG dependencies
validate_source >> [refresh_dim_case_type, refresh_dim_org, refresh_dim_time, refresh_dim_stakeholder]
[refresh_dim_case_type, refresh_dim_org, refresh_dim_time, refresh_dim_stakeholder] >> refresh_business_fact
[refresh_dim_case_type, refresh_dim_org, refresh_dim_time, refresh_dim_stakeholder] >> refresh_cashflow_fact
[refresh_business_fact, refresh_cashflow_fact] >> invalidate_cache >> record_sync
```

### 3.2 DAG 실행 순서

```
validate_source_data
        │
        ├─→ refresh_dim_case_type ────┐
        ├─→ refresh_dim_org ──────────┤
        ├─→ refresh_dim_time ─────────┤ (병렬)
        └─→ refresh_dim_stakeholder ──┤
                                       │
                    ┌──────────────────┤
                    ▼                  ▼
        refresh_business_fact  refresh_cashflow_fact
                    │                  │
                    └──────┬───────────┘
                           ▼
                 invalidate_redis_cache
                           │
                           ▼
                 record_sync_completion
```

---

## 4. MV REFRESH 중 가용성 보장

### 4.1 CONCURRENTLY 옵션

```sql
-- CONCURRENTLY requires a UNIQUE INDEX on the MV
CREATE UNIQUE INDEX idx_mv_business_fact_pk
  ON mv_business_fact (case_type_id, org_id, time_id, stk_type_id);

-- Non-blocking refresh
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_business_fact;
```

**CONCURRENTLY 장점**:
- 기존 MV 데이터로 읽기 쿼리 계속 가능
- 새 데이터가 준비되면 원자적으로 교체

**CONCURRENTLY 단점**:
- 일반 REFRESH보다 느림 (diff 계산 필요)
- UNIQUE INDEX 필수
- 첫 번째 REFRESH는 CONCURRENTLY 불가 (데이터 없는 상태)

### 4.2 모니터링

```python
# ETL sync monitoring
async def get_sync_health() -> dict:
    return {
        "last_full_sync": await get_last_sync_time("full"),
        "last_incremental_sync": await get_last_sync_time("incremental"),
        "views": [
            {
                "name": "mv_business_fact",
                "row_count": await get_mv_row_count("mv_business_fact"),
                "last_refreshed": await get_mv_last_refreshed("mv_business_fact"),
                "refresh_duration_ms": await get_last_refresh_duration("mv_business_fact"),
            }
        ],
        "health": "healthy" if await is_data_fresh(max_age_hours=25) else "stale"
    }
```

---

## 결정 사항 (Decisions)

- Materialized View 기반 ETL (ADR-003)
- CONCURRENTLY 옵션으로 무중단 갱신
- 디멘전 → 팩트 순서로 갱신 (외래키 일관성)
- Airflow DAG로 일일 스케줄링

## 금지 사항 (Forbidden)

- CONCURRENTLY 없이 REFRESH (읽기 차단 발생)
- 동시에 같은 MV 2회 REFRESH (advisory lock으로 방지)
- OLTP 테이블에 직접 OLAP 쿼리 (MV만 사용)

## 필수 사항 (Required)

- MV에 UNIQUE INDEX 생성 (CONCURRENTLY 전제)
- REFRESH 실패 시 3회 재시도
- REFRESH 후 Redis 캐시 무효화
- 동기화 이력 기록 (시작/완료 시간, 행 수, 소요 시간)

<!-- affects: 06_data/data-warehouse.md, 08_operations/deployment.md -->
