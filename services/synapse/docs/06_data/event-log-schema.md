# Event Log PostgreSQL 스키마

## 이 문서가 답하는 질문

- 이벤트 로그는 PostgreSQL에서 어떤 테이블로 저장되는가?
- 이벤트 로그 엔트리의 스키마와 인덱스 전략은?
- 프로세스 인스턴스(케이스)와 프로세스 변형(variant)은 어떻게 관리하는가?
- Conformance Checking 결과는 어디에 저장하는가?
- Neo4j 그래프와 PostgreSQL 테이블 간 데이터 분배 전략은?

<!-- affects: backend, api, data -->
<!-- requires-update: 02_api/event-log-api.md, 02_api/process-mining-api.md, 03_backend/process-discovery.md -->

---

## 1. 데이터 분배 전략

### 1.1 PostgreSQL vs Neo4j 역할

이벤트 로그 데이터는 대량의 시계열 데이터이므로 PostgreSQL에 저장한다. Neo4j에는 **분석 결과**만 저장한다.

| 데이터 유형 | 저장소 | 이유 |
|------------|--------|------|
| 이벤트 로그 원본 (수백만 행) | **PostgreSQL** | 대량 시계열 데이터, 집계 쿼리 최적화 |
| 이벤트 로그 메타데이터 | **PostgreSQL** | CRUD 관리, 인제스트 상태 추적 |
| 프로세스 인스턴스/변형 | **PostgreSQL** | 집계 통계, 페이지네이션 |
| Conformance 결과 | **PostgreSQL** | 결과 이력 관리, 비교 분석 |
| 발견된 프로세스 모델 | **Neo4j** | 그래프 탐색, 온톨로지 통합 |
| EventStorming 노드의 시간축 속성 | **Neo4j** | BusinessEvent 노드 속성으로 바인딩 |
| 활동 간 FOLLOWED_BY 관계 + 통계 | **Neo4j** | 그래프 경로 분석, 프로세스 플로우 시각화 |

### 1.2 데이터 흐름

```
CSV/XES/DB 소스
     │
     ▼
┌──────────────────┐    인제스트     ┌──────────────────┐
│  event_logs      │◄───────────────│  파일/DB 커넥션   │
│  (메타데이터)     │                └──────────────────┘
└────────┬─────────┘
         │ 1:N
         ▼
┌──────────────────┐    분석 실행    ┌──────────────────┐
│  event_log_      │───────────────▶│  pm4py DataFrame │
│  entries         │                │  (메모리)         │
│  (원본 이벤트)    │                └────────┬─────────┘
└──────────────────┘                         │
                                    ┌────────┴─────────┐
                                    │                  │
                                    ▼                  ▼
                           ┌──────────────┐   ┌──────────────┐
                           │ PostgreSQL   │   │ Neo4j        │
                           │ - variants   │   │ - 프로세스 모델│
                           │ - instances  │   │ - 시간축 속성  │
                           │ - conformance│   │ - FOLLOWED_BY │
                           └──────────────┘   └──────────────┘
```

---

## 2. 테이블 스키마

### 2.1 event_logs (이벤트 로그 메타데이터)

이벤트 로그 파일/소스의 메타데이터를 관리한다. 실제 이벤트 데이터는 `event_log_entries`에 저장한다.

```sql
CREATE TABLE event_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,                   -- Core tenants.id (JWT tenant_id)
    case_id         UUID NOT NULL,                   -- Axiom 프로젝트 ID
    name            VARCHAR(255) NOT NULL,           -- 이벤트 로그 이름
    description     TEXT,                            -- 설명
    source_type     VARCHAR(20) NOT NULL,            -- 'csv', 'xes', 'database'
    source_config   JSONB,                           -- 소스별 설정 (DB 연결 정보, 파일 경로 등)
    column_mapping  JSONB NOT NULL,                  -- 컬럼 매핑 설정
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 인제스트 상태
    statistics      JSONB,                           -- 인제스트 완료 후 통계
    error_message   TEXT,                            -- 실패 시 에러 메시지
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID                             -- 생성자 ID
);

-- Indexes
CREATE INDEX idx_event_logs_tenant_id ON event_logs(tenant_id);
CREATE INDEX idx_event_logs_case_id ON event_logs(tenant_id, case_id);
CREATE INDEX idx_event_logs_status ON event_logs(status);
CREATE INDEX idx_event_logs_created_at ON event_logs(created_at DESC);

-- RLS Policy (Core 4중 격리 모델과 동일한 GUC 변수 사용)
ALTER TABLE event_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY event_logs_tenant_isolation ON event_logs
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

#### status 상태 전이

```
pending → ingesting → completed
                    → failed
completed → refreshing → completed
                       → failed
```

| 상태 | 의미 | 전이 조건 |
|------|------|----------|
| `pending` | 생성됨, 인제스트 대기 | 초기 상태 |
| `ingesting` | 인제스트 진행 중 | POST /ingest 호출 시 |
| `completed` | 인제스트 완료 | 모든 이벤트 저장 성공 |
| `failed` | 인제스트 실패 | 파싱/저장 오류 발생 |
| `refreshing` | 재인제스트 진행 중 | POST /refresh 호출 시 (DB 소스만) |

#### column_mapping JSONB 구조

```json
{
  "case_id_column": "order_id",
  "activity_column": "event_type",
  "timestamp_column": "event_time",
  "resource_column": "handler_name",
  "additional_columns": ["department", "priority", "amount"]
}
```

#### source_config JSONB 구조 (source_type별)

```json
// source_type = "csv"
{
  "original_filename": "order_events_2024.csv",
  "file_size_bytes": 15728640,
  "encoding": "utf-8",
  "delimiter": ",",
  "timestamp_format": "ISO8601"
}

// source_type = "xes"
{
  "original_filename": "process_log.xes",
  "file_size_bytes": 8388608
}

// source_type = "database"
{
  "connection_id": "erp-connection-uuid",
  "table_name": "order_events",
  "schema": "public",
  "where_clause": "event_time >= '2024-01-01'",
  "max_rows": 1000000
}
```

#### statistics JSONB 구조 (인제스트 완료 후)

```json
{
  "total_events": 8750,
  "total_cases": 1250,
  "unique_activities": 6,
  "date_range_start": "2024-01-01T08:00:00Z",
  "date_range_end": "2024-06-30T17:30:00Z",
  "avg_events_per_case": 7.0,
  "ingestion_duration_seconds": 12.5
}
```

---

### 2.2 event_log_entries (이벤트 로그 엔트리)

개별 이벤트를 저장한다. Process Mining 분석 시 이 테이블에서 pm4py DataFrame으로 변환한다.

```sql
CREATE TABLE event_log_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    log_id          UUID NOT NULL REFERENCES event_logs(id) ON DELETE CASCADE,
    case_id         VARCHAR(255) NOT NULL,           -- 프로세스 케이스 식별자 (예: 주문번호)
    activity        VARCHAR(255) NOT NULL,           -- 활동명 (예: "주문 접수")
    timestamp       TIMESTAMPTZ NOT NULL,            -- 이벤트 발생 시각
    resource        VARCHAR(255),                    -- 수행자/담당자
    attributes      JSONB DEFAULT '{}',              -- 추가 속성 (department, priority, amount 등)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Core indexes for pm4py query patterns
CREATE INDEX idx_entries_log_id ON event_log_entries(log_id);
CREATE INDEX idx_entries_case_id ON event_log_entries(log_id, case_id);
CREATE INDEX idx_entries_activity ON event_log_entries(log_id, activity);
CREATE INDEX idx_entries_timestamp ON event_log_entries(log_id, timestamp);
CREATE INDEX idx_entries_case_timestamp ON event_log_entries(log_id, case_id, timestamp);

-- Partial index for resource-based queries
CREATE INDEX idx_entries_resource ON event_log_entries(log_id, resource)
    WHERE resource IS NOT NULL;
```

#### 인덱스 전략

| 인덱스 | 용도 | 쿼리 패턴 |
|--------|------|----------|
| `idx_entries_log_id` | 로그별 전체 이벤트 조회 | `SELECT * FROM ... WHERE log_id = $1` |
| `idx_entries_case_id` | 케이스별 이벤트 조회 | `WHERE log_id = $1 AND case_id = $2` |
| `idx_entries_activity` | 활동별 통계 | `WHERE log_id = $1 AND activity = $2` |
| `idx_entries_case_timestamp` | pm4py DataFrame 생성 (핵심) | `WHERE log_id = $1 ORDER BY case_id, timestamp` |
| `idx_entries_resource` | 리소스별 분석 | `WHERE log_id = $1 AND resource = $2` |

#### pm4py DataFrame 변환 쿼리

```sql
-- Process Mining 분석 시 전체 이벤트를 pm4py DataFrame으로 변환
SELECT
    case_id AS "case:concept:name",
    activity AS "concept:name",
    timestamp AS "time:timestamp",
    resource AS "org:resource",
    attributes
FROM event_log_entries
WHERE log_id = $1
ORDER BY case_id, timestamp;
```

---

### 2.3 process_instances (프로세스 인스턴스)

각 케이스(프로세스 인스턴스)의 요약 정보를 저장한다. `event_log_entries`에서 집계하여 생성한다.

```sql
CREATE TABLE process_instances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    log_id          UUID NOT NULL REFERENCES event_logs(id) ON DELETE CASCADE,
    case_id         VARCHAR(255) NOT NULL,           -- 프로세스 케이스 식별자
    variant_id      UUID REFERENCES process_variants(id),  -- 변형 그룹
    start_time      TIMESTAMPTZ NOT NULL,            -- 첫 이벤트 시각
    end_time        TIMESTAMPTZ NOT NULL,            -- 마지막 이벤트 시각
    duration_seconds DOUBLE PRECISION NOT NULL,      -- 총 소요시간 (초)
    event_count     INTEGER NOT NULL,                -- 이벤트 수
    activity_sequence TEXT[] NOT NULL,               -- 활동 순서 배열 ['주문접수', '결제확인', ...]
    is_conformant   BOOLEAN,                         -- Conformance Checking 적합 여부 (null = 미검사)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_instances_log_id ON process_instances(log_id);
CREATE INDEX idx_instances_variant ON process_instances(variant_id);
CREATE INDEX idx_instances_duration ON process_instances(log_id, duration_seconds);
CREATE UNIQUE INDEX idx_instances_log_case ON process_instances(log_id, case_id);
```

#### 생성 로직

```sql
-- event_log_entries에서 process_instances 집계 생성
INSERT INTO process_instances (log_id, case_id, start_time, end_time, duration_seconds, event_count, activity_sequence)
SELECT
    $1 AS log_id,
    case_id,
    MIN(timestamp) AS start_time,
    MAX(timestamp) AS end_time,
    EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) AS duration_seconds,
    COUNT(*) AS event_count,
    ARRAY_AGG(activity ORDER BY timestamp) AS activity_sequence
FROM event_log_entries
WHERE log_id = $1
GROUP BY case_id;
```

---

### 2.4 process_variants (프로세스 변형)

동일한 활동 순서를 가진 케이스 그룹이다. Variant Analysis의 기반 데이터이다.

```sql
CREATE TABLE process_variants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    log_id          UUID NOT NULL REFERENCES event_logs(id) ON DELETE CASCADE,
    activity_sequence TEXT[] NOT NULL,               -- 활동 순서 배열
    activity_sequence_hash VARCHAR(64) NOT NULL,     -- 활동 순서 SHA-256 해시 (중복 방지)
    case_count      INTEGER NOT NULL DEFAULT 0,      -- 이 변형에 속하는 케이스 수
    relative_frequency DOUBLE PRECISION NOT NULL DEFAULT 0, -- 상대 빈도 (0.0 - 1.0)
    avg_duration_seconds DOUBLE PRECISION,           -- 평균 소요시간 (초)
    median_duration_seconds DOUBLE PRECISION,        -- 중위 소요시간 (초)
    min_duration_seconds DOUBLE PRECISION,           -- 최소 소요시간 (초)
    max_duration_seconds DOUBLE PRECISION,           -- 최대 소요시간 (초)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_variants_log_id ON process_variants(log_id);
CREATE INDEX idx_variants_case_count ON process_variants(log_id, case_count DESC);
CREATE UNIQUE INDEX idx_variants_log_hash ON process_variants(log_id, activity_sequence_hash);
```

#### Variant 생성 로직

```sql
-- process_instances에서 process_variants 집계 생성
WITH variant_groups AS (
    SELECT
        log_id,
        activity_sequence,
        encode(sha256(array_to_string(activity_sequence, '→')::bytea), 'hex') AS seq_hash,
        COUNT(*) AS case_count,
        AVG(duration_seconds) AS avg_duration,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_seconds) AS median_duration,
        MIN(duration_seconds) AS min_duration,
        MAX(duration_seconds) AS max_duration
    FROM process_instances
    WHERE log_id = $1
    GROUP BY log_id, activity_sequence
)
INSERT INTO process_variants (
    log_id, activity_sequence, activity_sequence_hash,
    case_count, relative_frequency,
    avg_duration_seconds, median_duration_seconds,
    min_duration_seconds, max_duration_seconds
)
SELECT
    log_id, activity_sequence, seq_hash,
    case_count,
    case_count::double precision / SUM(case_count) OVER () AS relative_frequency,
    avg_duration, median_duration, min_duration, max_duration
FROM variant_groups;
```

#### Variant 데이터 예시

| activity_sequence | case_count | relative_frequency | avg_duration |
|-------------------|------------|-------------------|--------------|
| {주문접수, 결제확인, 재고확인, 출하지시, 배송완료} | 850 | 0.68 | 172800 |
| {주문접수, 결제확인, 출하지시, 배송완료} | 200 | 0.16 | 86400 |
| {주문접수, 결제확인, 재고확인, 반품처리, 환불} | 120 | 0.096 | 259200 |

---

### 2.5 conformance_results (Conformance Checking 결과)

Conformance Checking 분석 결과를 이력으로 관리한다. 동일 로그에 대해 여러 번 실행 가능하다.

```sql
CREATE TABLE conformance_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    log_id          UUID NOT NULL REFERENCES event_logs(id) ON DELETE CASCADE,
    model_id        VARCHAR(255) NOT NULL,           -- 참조 모델 ID (Neo4j EventStorming 모델)
    model_type      VARCHAR(50) NOT NULL DEFAULT 'eventstorming',  -- 모델 유형
    algorithm       VARCHAR(50) NOT NULL DEFAULT 'token_based_replay',  -- 알고리즘
    fitness         DOUBLE PRECISION NOT NULL,       -- Fitness (0.0 - 1.0)
    precision_score DOUBLE PRECISION NOT NULL,       -- Precision (0.0 - 1.0), 'precision' is reserved
    generalization  DOUBLE PRECISION NOT NULL,       -- Generalization (0.0 - 1.0)
    simplicity      DOUBLE PRECISION,                -- Simplicity (0.0 - 1.0)
    total_cases     INTEGER NOT NULL,                -- 분석된 총 케이스 수
    conformant_cases INTEGER NOT NULL,               -- 적합한 케이스 수
    deviation_summary JSONB,                         -- 편차 요약 (skipped/unexpected 통계)
    parameters      JSONB DEFAULT '{}',              -- 분석 파라미터
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checked_by      UUID                             -- 실행자 ID
);

-- Indexes
CREATE INDEX idx_conformance_log_id ON conformance_results(log_id);
CREATE INDEX idx_conformance_model ON conformance_results(model_id);
CREATE INDEX idx_conformance_checked_at ON conformance_results(log_id, checked_at DESC);
```

#### deviation_summary JSONB 구조

```json
{
  "total_deviations": 245,
  "skipped_activities": {
    "재고 확인": 120,
    "품질 검사": 45
  },
  "unexpected_activities": {
    "반품 처리": 23,
    "긴급 출하": 57
  },
  "non_conformant_case_ids": ["ORD-2024-102", "ORD-2024-203"]
}
```

#### parameters JSONB 구조

```json
{
  "discovery_algorithm": "inductive",
  "noise_threshold": 0.2,
  "include_case_diagnostics": true,
  "max_diagnostics_cases": 100
}
```

---

## 3. 테이블 관계 다이어그램

```
┌──────────────┐
│  event_logs  │
│  (메타데이터)  │
└──────┬───────┘
       │
       ├── 1:N ──▶ ┌───────────────────┐
       │            │  event_log_entries │
       │            │  (원본 이벤트)      │
       │            └───────────────────┘
       │
       ├── 1:N ──▶ ┌───────────────────┐     ┌───────────────────┐
       │            │  process_instances │──▶  │  process_variants │
       │            │  (케이스 요약)      │ N:1 │  (변형 그룹)       │
       │            └───────────────────┘     └───────────────────┘
       │                                              ▲
       │                                              │ 1:N
       ├── 1:N ──▶ ┌───────────────────┐              │
                    │ conformance_      │              │
                    │ results           │──────────────┘ (variant 참조)
                    │ (적합도 결과)      │
                    └───────────────────┘
```

---

## 4. 데이터 생명주기

### 4.1 인제스트 → 분석 → 삭제 흐름

```
1. POST /ingest
   → event_logs (status: ingesting)
   → event_log_entries (벌크 INSERT)
   → event_logs (status: completed, statistics 갱신)

2. POST /discover 또는 POST /conformance
   → event_log_entries → pm4py DataFrame (메모리)
   → process_instances (집계 생성/갱신)
   → process_variants (집계 생성/갱신)
   → conformance_results (Conformance 시)
   → Neo4j (발견된 프로세스 모델, 시간축 속성)

3. DELETE /{log_id}
   → event_log_entries (CASCADE 삭제)
   → process_instances (CASCADE 삭제)
   → process_variants (CASCADE 삭제)
   → conformance_results (CASCADE 삭제)
   → event_logs (삭제)
   → Neo4j 모델은 유지 (source: 'discovered' 노드는 별도 관리)
```

### 4.2 데이터 보존 정책

| 데이터 유형 | 보존 기간 | 삭제 방식 |
|------------|----------|----------|
| event_log_entries | 이벤트 로그 삭제 시 | CASCADE |
| process_instances | 이벤트 로그 삭제 시 | CASCADE |
| process_variants | 이벤트 로그 삭제 시 | CASCADE |
| conformance_results | 이벤트 로그 삭제 시 | CASCADE |
| Neo4j 발견 모델 | 수동 삭제 | Graph API 경유 |

---

## 5. 성능 고려사항

### 5.1 대용량 이벤트 로그 처리

| 규모 | 이벤트 수 | 처리 방식 | 예상 인제스트 시간 |
|------|----------|----------|-----------------|
| 소규모 | < 10,000 | 동기 벌크 INSERT | < 5초 |
| 중규모 | 10,000 - 100,000 | 비동기 배치 INSERT (1,000건 단위) | 10 - 60초 |
| 대규모 | 100,000 - 1,000,000 | 비동기 COPY (PostgreSQL COPY) | 1 - 5분 |
| 초대규모 | > 1,000,000 | 비동기 COPY + 파티셔닝 검토 | 5분+ |

### 5.2 인제스트 배치 처리

```python
async def bulk_insert_events(
    pool: asyncpg.Pool,
    log_id: str,
    events: list[dict],
    batch_size: int = 1000
) -> int:
    """
    Bulk insert events with batching for large datasets.
    Uses PostgreSQL COPY for optimal performance.
    """
    total_inserted = 0

    async with pool.acquire() as conn:
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            records = [
                (log_id, e['case_id'], e['activity'], e['timestamp'],
                 e.get('resource'), json.dumps(e.get('attributes', {})))
                for e in batch
            ]

            await conn.copy_records_to_table(
                'event_log_entries',
                records=records,
                columns=['log_id', 'case_id', 'activity', 'timestamp',
                         'resource', 'attributes']
            )
            total_inserted += len(batch)

    return total_inserted
```

### 5.3 파티셔닝 전략 (향후)

100만 이벤트 초과 로그가 빈번할 경우 `event_log_entries`를 `log_id` 기준으로 해시 파티셔닝한다.

```sql
-- 향후 파티셔닝 적용 시
CREATE TABLE event_log_entries (
    -- ... columns ...
) PARTITION BY HASH (log_id);

CREATE TABLE event_log_entries_p0 PARTITION OF event_log_entries
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
-- ... p1, p2, p3
```

> **결정 상태**: 미결정. 현재는 단일 테이블로 운영하며, 성능 병목 발생 시 파티셔닝을 적용한다.

---

## 금지 규칙

- `event_log_entries`에 인덱스 없이 전체 테이블 스캔을 실행하지 않는다
- pm4py 분석 시 `event_log_entries`를 직접 쿼리하지 않는다 (반드시 서비스 레이어 경유)
- `source_config`에 DB 비밀번호를 평문으로 저장하지 않는다 (connection_id 참조만 허용)
- CASCADE 삭제 범위를 확인하지 않고 `event_logs`를 삭제하지 않는다

## 필수 규칙

- 인제스트 완료 후 반드시 `statistics` JSONB를 갱신한다
- `process_instances`와 `process_variants`는 분석 실행 시 재생성한다 (이전 결과 UPSERT)
- 모든 테이블에 `log_id` 기반 인덱스를 포함한다 (멀티테넌트 격리)
- `conformance_results`는 삭제하지 않고 이력으로 누적한다

---

## 근거 문서

- `02_api/event-log-api.md` (Event Log 관리 API)
- `02_api/process-mining-api.md` (Process Mining API)
- `03_backend/process-discovery.md` (Process Discovery 구현)
- `03_backend/conformance-checker.md` (Conformance Checker 구현)
- `06_data/neo4j-schema.md` (Neo4j 스키마 - 분석 결과 저장)
- ADR-005: pm4py 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
