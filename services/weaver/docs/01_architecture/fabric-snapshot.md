# 패브릭 스냅샷 아키텍처

<!-- affects: backend, data, api -->
<!-- requires-update: 02_api/metadata-api.md, 06_data/neo4j-schema.md -->

## 이 문서가 답하는 질문

- 패브릭 스냅샷이란 무엇인가?
- 스냅샷은 언제, 어떻게 생성되는가?
- 두 스냅샷 간의 차이를 어떻게 비교하는가?
- 스냅샷으로 메타데이터를 어떻게 복원하는가?
- 스냅샷 보존 정책은 어떠한가?
- 멀티테넌트 환경에서 스냅샷 격리는?

---

## 1. 개념 정의

### 1.1 패브릭 스냅샷이란

패브릭 스냅샷(Fabric Snapshot)은 **특정 시점의 메타데이터 그래프 상태를 직렬화하여 보존하는 구조**이다.

비유하자면 **데이터베이스 스키마에 대한 git commit**이다. 소스 코드를 커밋하듯, 메타데이터 그래프의 현재 상태를 "찍어두는" 것이다. 이후 임의 시점의 스냅샷과 비교(diff)하거나, 과거 스냅샷으로 복원(restore)할 수 있다.

**캡처 대상**:

| 항목 | 예시 |
|------|------|
| 테이블 목록 | `public.processes`, `public.organizations` |
| 컬럼 정의 | `id: bigint NOT NULL PK`, `org_id: bigint NOT NULL FK` |
| 데이터 타입 | `varchar(50)`, `timestamptz`, `boolean` |
| FK 관계 | `processes.org_id -> organizations.id` |
| 테이블/컬럼 설명 | LLM이 보강한 한국어 설명 포함 |
| 태그 | `["pii"]`, `["core", "audit-required"]` |
| 행 수 추정치 | `row_count: 15420` |
| 스키마 구조 | `public`, `operations`, `audit` |

```
                    ┌──────────────────────────────────────────────┐
                    │          원본 DB (PostgreSQL 등)               │
                    │                                               │
                    │  실제 데이터 행 (15,420건)                     │
                    │  ┌──────────────────────────────────┐        │
                    │  │ id │ process_code │ org_id │ ... │        │
                    │  │ 1  │ PROC-001     │ 42     │ ... │        │
                    │  │ 2  │ PROC-002     │ 43     │ ... │  ← 이건 캡처 안 함
                    │  │ .. │ ...          │ ...    │ ... │        │
                    │  └──────────────────────────────────┘        │
                    └──────────────────────────────────────────────┘
                                         │
                                         ▼
                    ┌──────────────────────────────────────────────┐
                    │          Neo4j 메타데이터 그래프                │
                    │                                               │
                    │  (:DataSource)-[:HAS_SCHEMA]->(:Schema)      │
                    │  (:Schema)-[:HAS_TABLE]->(:Table)            │
                    │  (:Table)-[:HAS_COLUMN]->(:Column)           │
                    │  (:Column)-[:FK_TO]->(:Column)               │
                    │                                               │
                    │  ← 이 그래프 구조 전체를 JSON으로 직렬화       │
                    └──────────────────────────────────────────────┘
                                         │
                                         ▼
                    ┌──────────────────────────────────────────────┐
                    │         :FabricSnapshot 노드                   │
                    │                                               │
                    │  { snapshot_id: "uuid-...",                   │
                    │    version: 7,                                │
                    │    graph_data: "{...직렬화된 전체 메타그래프}" } │
                    │                                               │
                    │  ← 이것이 패브릭 스냅샷                        │
                    └──────────────────────────────────────────────┘
```

### 1.2 스냅샷이 캡처하지 않는 것

| 항목 | 이유 |
|------|------|
| 실제 데이터 행 | 스냅샷은 구조 메타데이터만 대상. 데이터 백업은 별도 시스템의 책임 |
| 쿼리 실행 결과 | 런타임 산출물 (캐시/결과셋은 Oracle/Vision 관할) |
| MindsDB 연결 상태 | MindsDB 핸들러 상태는 휘발성. CREATE DATABASE로 재생성 가능 |
| Oracle 벡터 인덱스 | 파생 데이터. 메타데이터 변경 이벤트 전파 시 Oracle이 자동 재생성 |
| 비밀번호/인증 정보 | 보안 정책상 Neo4j에 저장하지 않음 (기존 정책 준수) |
| 물리화 테이블 (Materialized Table) | MindsDB 내부 테이블. 스냅샷 범위 밖 |

### 1.3 사용 시나리오

| 시나리오 | 설명 | 트리거 |
|----------|------|--------|
| **스키마 마이그레이션 추적** | "ERP DB가 v3.2에서 v4.0으로 업그레이드 -- 어떤 컬럼이 변경되었나?" | 수동/자동 |
| **감사 규정 준수** | "2025년 12월 31일 시점의 테이블 구조 기록이 필요합니다" | 스케줄 |
| **잘못된 추출 롤백** | "메타데이터 추출이 잘못된 스키마를 가져왔다 -- 이전 스냅샷으로 복원" | 수동 |
| **변경 영향도 분석** | "지난 분기 대비 추가/삭제된 테이블은? 컬럼 타입 변경은?" | 수동 |
| **CI/CD 스키마 검증** | "배포 전후 메타데이터 diff가 예상과 일치하는지 자동 검증" | 자동 |

---

## 2. 스냅샷 데이터 모델

### 2.1 :FabricSnapshot 노드

Neo4j 그래프 내에 `:FabricSnapshot` 레이블로 저장된다.

```cypher
(:FabricSnapshot {
    snapshot_id: "550e8400-e29b-41d4-a716-446655440000",  -- String (UUID), UNIQUE, NOT NULL
    tenant_id: "t-001-uuid",                               -- String (UUID), NOT NULL
    case_id: "c-001-uuid",                                 -- String (UUID), NOT NULL
    datasource_name: "erp_db",                              -- String, NOT NULL
    version: 7,                                             -- Integer, NOT NULL (per-datasource auto-increment)
    trigger_type: "auto",                                   -- String, NOT NULL ("manual"|"auto"|"scheduled")
    status: "completed",                                    -- String, NOT NULL ("creating"|"completed"|"failed")
    created_at: datetime("2026-02-20T10:00:00Z"),          -- DateTime, NOT NULL
    created_by: "admin@axiom.kr",                           -- String, NOT NULL
    graph_data: '{"version":"2.0",...}',                    -- String (JSON), NOT NULL
    description: "v4.0 마이그레이션 전 스냅샷",              -- String, nullable
    is_locked: false,                                       -- Boolean, NOT NULL (default: false)
    size_bytes: 52480                                       -- Integer, NOT NULL
})
```

| 속성 | 타입 | nullable | 인덱스 | 설명 |
|------|------|----------|--------|------|
| `snapshot_id` | String (UUID) | No | UNIQUE | 스냅샷 글로벌 고유 식별자 |
| `tenant_id` | String (UUID) | No | INDEX (복합) | JWT에서 추출한 테넌트 ID |
| `case_id` | String (UUID) | No | INDEX (복합) | 프로젝트/케이스 범위 |
| `datasource_name` | String | No | INDEX (복합) | 대상 데이터소스 이름 |
| `version` | Integer | No | - | 해당 데이터소스 내 순차 버전 번호 (1, 2, 3, ...) |
| `trigger_type` | String | No | - | `manual` / `auto` / `scheduled` |
| `status` | String | No | INDEX | `creating` / `completed` / `failed` |
| `created_at` | DateTime | No | INDEX | 생성 시각 (UTC) |
| `created_by` | String | No | - | 생성한 사용자 이메일 또는 `system` |
| `graph_data` | String (JSON) | No | - | 직렬화된 전체 메타데이터 서브그래프 |
| `description` | String | Yes | - | 사용자 입력 설명 |
| `is_locked` | Boolean | No | - | `true`이면 보존 정책에 의한 자동 삭제 대상에서 제외 |
| `size_bytes` | Integer | No | - | `graph_data` JSON 문자열의 바이트 크기 |

**관계**:

```cypher
(:DataSource)-[:HAS_SNAPSHOT]->(:FabricSnapshot)
```

```
(:DataSource {name: "erp_db", tenant_id: "t-001", case_id: "c-001"})
    │
    │ :HAS_SNAPSHOT
    ▼
(:FabricSnapshot {snapshot_id: "snap-001", version: 1, ...})
(:FabricSnapshot {snapshot_id: "snap-002", version: 2, ...})
(:FabricSnapshot {snapshot_id: "snap-003", version: 3, ...})
    ...
(:FabricSnapshot {snapshot_id: "snap-007", version: 7, ...})  ← 최신
```

**인덱스와 제약조건**:

```cypher
-- 스냅샷 고유 식별자
CREATE CONSTRAINT snapshot_id_unique IF NOT EXISTS
    FOR (fs:FabricSnapshot) REQUIRE fs.snapshot_id IS UNIQUE;

-- 테넌트+케이스+데이터소스 복합 인덱스 (목록 조회 성능)
CREATE INDEX snapshot_tenant_ds_idx IF NOT EXISTS
    FOR (fs:FabricSnapshot) ON (fs.tenant_id, fs.case_id, fs.datasource_name);

-- 상태별 조회 인덱스
CREATE INDEX snapshot_status_idx IF NOT EXISTS
    FOR (fs:FabricSnapshot) ON (fs.status);

-- 생성일 기준 정렬/필터용 인덱스
CREATE INDEX snapshot_created_idx IF NOT EXISTS
    FOR (fs:FabricSnapshot) ON (fs.created_at);
```

### 2.2 graph_data 포맷

`graph_data`는 JSON 문자열로 직렬화된 전체 메타데이터 서브그래프이다. 포맷 버전은 `2.0`이다.

```json
{
  "version": "2.0",
  "captured_at": "2026-02-20T10:00:00Z",
  "datasource": {
    "name": "erp_db",
    "engine": "postgresql",
    "host": "erp-db.internal",
    "port": 5432,
    "database": "enterprise_ops",
    "user": "reader",
    "last_extracted": "2026-02-20T09:55:00Z"
  },
  "schemas": [
    {
      "name": "public",
      "tables": [
        {
          "name": "processes",
          "description": "비즈니스 프로세스 정보",
          "row_count": 15420,
          "table_type": "BASE TABLE",
          "columns": [
            {
              "name": "id",
              "dtype": "bigint",
              "nullable": false,
              "is_primary_key": true,
              "default_value": "nextval('processes_id_seq'::regclass)",
              "description": "프로세스 고유 ID"
            },
            {
              "name": "process_code",
              "dtype": "varchar(50)",
              "nullable": false,
              "is_primary_key": false,
              "default_value": null,
              "description": "프로세스 코드 (예: PROC-2026-001)"
            },
            {
              "name": "org_id",
              "dtype": "bigint",
              "nullable": false,
              "is_primary_key": false,
              "default_value": null,
              "description": "대상 조직 ID (FK)"
            }
          ]
        },
        {
          "name": "organizations",
          "description": "대상 조직 정보",
          "row_count": 8750,
          "table_type": "BASE TABLE",
          "columns": [
            {
              "name": "id",
              "dtype": "bigint",
              "nullable": false,
              "is_primary_key": true,
              "default_value": null,
              "description": "조직 고유 ID"
            },
            {
              "name": "name",
              "dtype": "varchar(100)",
              "nullable": false,
              "is_primary_key": false,
              "default_value": null,
              "description": "조직명/상호"
            },
            {
              "name": "business_number",
              "dtype": "varchar(12)",
              "nullable": true,
              "is_primary_key": false,
              "default_value": null,
              "description": "사업자등록번호"
            }
          ]
        }
      ]
    }
  ],
  "foreign_keys": [
    {
      "source_schema": "public",
      "source_table": "processes",
      "source_column": "org_id",
      "target_schema": "public",
      "target_table": "organizations",
      "target_column": "id",
      "constraint_name": "fk_process_org"
    },
    {
      "source_schema": "public",
      "source_table": "transactions",
      "source_column": "process_id",
      "target_schema": "public",
      "target_table": "processes",
      "target_column": "id",
      "constraint_name": "fk_transaction_process"
    }
  ],
  "tags": {
    "public.processes": ["core", "audit-required"],
    "public.organizations": ["core"],
    "public.organizations.business_number": ["pii"],
    "public.stakeholders.ssn": ["pii", "encrypted"]
  },
  "statistics": {
    "total_schemas": 3,
    "total_tables": 45,
    "total_columns": 312,
    "total_fks": 28,
    "total_tagged_items": 4
  }
}
```

**포맷 호환성 정책**:

- `version` 필드로 하위 호환성 관리
- `2.x` 간에는 필드 추가만 허용 (기존 필드 삭제/타입 변경 금지)
- `3.0` 등 메이저 버전 변경 시 마이그레이션 스크립트 필수

### 2.3 :SnapshotDiff 노드

두 스냅샷 간의 차이를 계산한 결과를 캐싱한다. 동일 쌍에 대한 반복 diff 요청 시 재계산을 방지한다.

```cypher
(:SnapshotDiff {
    diff_id: "diff-uuid-001",                           -- String (UUID), UNIQUE
    tenant_id: "t-001-uuid",                             -- String (UUID), NOT NULL
    case_id: "c-001-uuid",                               -- String (UUID), NOT NULL
    datasource_name: "erp_db",                            -- String, NOT NULL
    base_snapshot_id: "snap-uuid-005",                    -- String (UUID), NOT NULL (이전 스냅샷)
    target_snapshot_id: "snap-uuid-007",                  -- String (UUID), NOT NULL (이후 스냅샷)
    diff_data: '{"tables_added":[...],...}',              -- String (JSON), NOT NULL
    created_at: datetime("2026-02-20T11:00:00Z")         -- DateTime, NOT NULL
})
```

**관계**:

```cypher
(:FabricSnapshot)-[:DIFF_BASE]->(:SnapshotDiff)
(:FabricSnapshot)-[:DIFF_TARGET]->(:SnapshotDiff)
```

```
(:FabricSnapshot {version: 5})
    │
    │ :DIFF_BASE
    ▼
(:SnapshotDiff {diff_id: "diff-001"})
    ▲
    │ :DIFF_TARGET
    │
(:FabricSnapshot {version: 7})
```

**diff_data 포맷**:

```json
{
  "base_version": 5,
  "target_version": 7,
  "base_captured_at": "2026-02-18T10:00:00Z",
  "target_captured_at": "2026-02-20T10:00:00Z",
  "summary": {
    "tables_added": 2,
    "tables_removed": 1,
    "columns_added": 8,
    "columns_removed": 3,
    "columns_modified": 5,
    "fks_added": 1,
    "fks_removed": 0,
    "descriptions_changed": 12,
    "tags_changed": 3
  },
  "details": {
    "tables_added": [
      {
        "schema": "public",
        "table": "audit_logs",
        "column_count": 6,
        "columns": ["id", "action", "user_id", "target", "detail", "created_at"]
      }
    ],
    "tables_removed": [
      {
        "schema": "public",
        "table": "legacy_temp",
        "column_count": 3
      }
    ],
    "columns_added": [
      {
        "schema": "public",
        "table": "processes",
        "column": "priority",
        "dtype": "integer",
        "nullable": true
      }
    ],
    "columns_removed": [
      {
        "schema": "public",
        "table": "processes",
        "column": "old_status_code",
        "dtype": "varchar(10)"
      }
    ],
    "columns_modified": [
      {
        "schema": "public",
        "table": "organizations",
        "column": "name",
        "changes": {
          "dtype": {"from": "varchar(100)", "to": "varchar(200)"},
          "nullable": {"from": false, "to": false}
        }
      }
    ],
    "fks_added": [
      {
        "source": "public.audit_logs.user_id",
        "target": "public.stakeholders.id",
        "constraint_name": "fk_audit_user"
      }
    ],
    "fks_removed": [],
    "descriptions_changed": [
      {
        "path": "public.processes",
        "type": "table",
        "from": "비즈니스 프로세스 정보",
        "to": "비즈니스 프로세스 마스터 테이블"
      },
      {
        "path": "public.processes.org_id",
        "type": "column",
        "from": "대상 조직 ID (FK)",
        "to": "대상 조직 ID (FK) - organizations.id 참조"
      }
    ],
    "tags_changed": [
      {
        "path": "public.audit_logs",
        "from": [],
        "to": ["compliance", "immutable"]
      }
    ]
  }
}
```

---

## 3. 스냅샷 생성 흐름

### 3.1 생성 트리거

| 트리거 | 설명 | 구현 방식 | API |
|--------|------|-----------|-----|
| `manual` | 사용자가 명시적으로 스냅샷 생성 요청 | REST API 호출 | `POST /api/v1/metadata/{datasource}/snapshots` |
| `auto` | 메타데이터 추출 완료 후 자동 생성 | SSE `complete` 이벤트 핸들러 내부에서 호출 | 내부 함수 호출 |
| `scheduled` | 크론 표현식에 따른 주기적 생성 | APScheduler 또는 Celery Beat | 내부 태스크 |

**자동 생성 트리거 연동 (extract-metadata SSE complete 후)**:

```python
# services/introspection_service.py 내부 (기존 extract-metadata 완료 핸들러에 추가)

async def _on_extraction_complete(
    self,
    tenant_id: str,
    case_id: str,
    datasource_name: str,
    extraction_result: dict,
):
    """메타데이터 추출 완료 후 자동 스냅샷 생성"""
    # SSE complete 이벤트 발행 후 백그라운드로 스냅샷 생성
    await self.snapshot_service.create_snapshot(
        tenant_id=tenant_id,
        case_id=case_id,
        datasource_name=datasource_name,
        trigger_type="auto",
        created_by="system",
        description=f"자동 스냅샷: 메타데이터 추출 완료 ({extraction_result['tables']} 테이블)",
    )
```

**스케줄 트리거 설정 예시**:

```python
# app/tasks/scheduled_snapshots.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# 매일 자정 (UTC) 모든 활성 데이터소스에 대해 스냅샷 생성
scheduler.add_job(
    create_scheduled_snapshots,
    trigger=CronTrigger(hour=0, minute=0),
    id="daily_fabric_snapshot",
    name="일간 패브릭 스냅샷",
    replace_existing=True,
)

async def create_scheduled_snapshots():
    """모든 테넌트의 활성 데이터소스에 대해 스케줄 스냅샷 생성"""
    active_datasources = await metadata_store.list_active_datasources()
    for ds in active_datasources:
        await snapshot_service.create_snapshot(
            tenant_id=ds["tenant_id"],
            case_id=ds["case_id"],
            datasource_name=ds["name"],
            trigger_type="scheduled",
            created_by="system",
        )
```

### 3.2 생성 알고리즘

```
사용자/시스템
    │
    │  POST /api/v1/metadata/{datasource}/snapshots
    │  또는 내부 함수 호출
    │
    ▼
┌─ 1. 입력 검증 ──────────────────────────────────────────────────────────┐
│                                                                          │
│  - tenant_id, case_id 존재 확인 (JWT에서 추출)                            │
│  - datasource_name에 해당하는 :DataSource 노드가 존재하는지 검증           │
│  - 현재 status="creating" 상태인 스냅샷이 있으면 409 Conflict 반환        │
│                                                                          │
└────────────┬─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─ 2. 스냅샷 노드 생성 (status: "creating") ───────────────────────────────┐
│                                                                          │
│  snapshot_id = uuid4()                                                   │
│  version = (현재 최대 version + 1)                                       │
│                                                                          │
│  Cypher:                                                                 │
│  MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid, case_id: $cid}) │
│  CREATE (ds)-[:HAS_SNAPSHOT]->(fs:FabricSnapshot {                      │
│      snapshot_id: $snapshot_id,                                          │
│      tenant_id: $tid,                                                    │
│      case_id: $cid,                                                      │
│      datasource_name: $ds_name,                                          │
│      version: $next_version,                                             │
│      trigger_type: $trigger_type,                                        │
│      status: "creating",                                                 │
│      created_at: datetime(),                                             │
│      created_by: $user,                                                  │
│      graph_data: "",                                                     │
│      is_locked: false,                                                   │
│      size_bytes: 0                                                       │
│  })                                                                      │
│  RETURN fs.snapshot_id                                                   │
│                                                                          │
└────────────┬─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─ 3. 메타데이터 서브그래프 읽기 (읽기 전용 트랜잭션) ──────────────────────┐
│                                                                          │
│  Cypher (단일 쿼리로 전체 서브그래프 수집):                                │
│                                                                          │
│  MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid, case_id: $cid}) │
│  OPTIONAL MATCH (ds)-[:HAS_SCHEMA]->(s:Schema)                          │
│  OPTIONAL MATCH (s)-[:HAS_TABLE]->(t:Table)                             │
│  OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)                           │
│  WITH ds, s, t, collect({                                                │
│      name: c.name, dtype: c.dtype, nullable: c.nullable,                │
│      description: c.description, is_primary_key: c.is_primary_key,      │
│      default_value: c.default_value                                      │
│  }) as columns                                                           │
│  WITH ds, s, collect({                                                   │
│      name: t.name, description: t.description,                          │
│      row_count: t.row_count, table_type: t.table_type,                  │
│      columns: columns                                                    │
│  }) as tables                                                            │
│  WITH ds, collect({name: s.name, tables: tables}) as schemas            │
│  RETURN ds, schemas                                                      │
│                                                                          │
│  FK 관계 별도 수집:                                                       │
│  MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid, case_id: $cid}) │
│      -[:HAS_SCHEMA]->(s1:Schema)                                        │
│      -[:HAS_TABLE]->(t1:Table)                                          │
│      -[:HAS_COLUMN]->(c1:Column)                                        │
│      -[:FK_TO]->(c2:Column)                                             │
│      <-[:HAS_COLUMN]-(t2:Table)                                         │
│      <-[:HAS_TABLE]-(s2:Schema)                                         │
│  RETURN s1.name as source_schema, t1.name as source_table,              │
│         c1.name as source_column, s2.name as target_schema,             │
│         t2.name as target_table, c2.name as target_column               │
│                                                                          │
└────────────┬─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─ 4. Python에서 graph_data JSON 직렬화 ───────────────────────────────────┐
│                                                                          │
│  graph_data = serialize_graph_data(                                       │
│      datasource=ds_record,                                               │
│      schemas=schema_records,                                             │
│      foreign_keys=fk_records,                                            │
│      tags=tag_records,                                                   │
│  )                                                                       │
│  # JSON 직렬화는 Python (orjson) 에서 수행                                │
│  # Neo4j Cypher 내 JSON 생성은 메모리 비효율적이므로 사용하지 않음         │
│                                                                          │
│  size_bytes = len(graph_data.encode("utf-8"))                            │
│                                                                          │
└────────────┬─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─ 5. 스냅샷 노드 업데이트 (status: "completed") ──────────────────────────┐
│                                                                          │
│  MATCH (fs:FabricSnapshot {snapshot_id: $snapshot_id})                   │
│  SET fs.graph_data = $graph_data,                                        │
│      fs.size_bytes = $size_bytes,                                        │
│      fs.status = "completed"                                             │
│                                                                          │
└────────────┬─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─ 6. Redis Stream 이벤트 발행 ─────────────────────────────────────────────┐
│                                                                          │
│  XADD axiom:metadata_changes * \                                         │
│      event "metadata.snapshot.created" \                                  │
│      tenant_id "t-001-uuid" \                                            │
│      case_id "c-001-uuid" \                                              │
│      datasource_name "erp_db" \                                          │
│      snapshot_id "snap-uuid-007" \                                       │
│      version "7" \                                                       │
│      trigger_type "auto"                                                 │
│                                                                          │
└────────────┬─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─ 7. 보존 정책 적용 (비동기) ──────────────────────────────────────────────┐
│                                                                          │
│  await enforce_retention_policy(tenant_id, case_id, datasource_name)     │
│  # 초과 스냅샷 자동 정리 (is_locked=false인 것만)                         │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.3 생성 서비스 구현 (의사 코드)

```python
# app/services/snapshot_service.py
import uuid
import time
import orjson
from datetime import datetime, timezone

from app.neo4j.metadata_store import MetadataStore
from app.events.redis_publisher import RedisPublisher
from app.core.errors import WeaverError


class SnapshotService:
    """패브릭 스냅샷 생성/조회/복원/삭제 서비스"""

    def __init__(self, metadata_store: MetadataStore, redis: RedisPublisher):
        self.store = metadata_store
        self.redis = redis

    async def create_snapshot(
        self,
        tenant_id: str,
        case_id: str,
        datasource_name: str,
        trigger_type: str,      # "manual" | "auto" | "scheduled"
        created_by: str,
        description: str = None,
    ) -> dict:
        """스냅샷 생성 (전체 흐름)

        1. 중복 생성 방지 (status=creating 확인)
        2. 스냅샷 노드 예약 생성
        3. 읽기 전용 트랜잭션으로 서브그래프 수집
        4. Python에서 JSON 직렬화
        5. 스냅샷 노드 업데이트
        6. Redis 이벤트 발행
        7. 보존 정책 적용
        """
        start = time.monotonic()

        # 0. DataSource 존재 확인
        ds = await self.store.get_datasource(tenant_id, case_id, datasource_name)
        if not ds:
            raise DataSourceNotFoundError(datasource_name)

        # 1. 동시 생성 방지
        creating = await self._get_creating_snapshot(tenant_id, case_id, datasource_name)
        if creating:
            raise WeaverError(
                code="SNAPSHOT_IN_PROGRESS",
                message=f"스냅샷 생성이 이미 진행 중입니다 (snapshot_id={creating})",
                status_code=409,
            )

        # 2. 스냅샷 노드 예약
        snapshot_id = str(uuid.uuid4())
        next_version = await self._get_next_version(tenant_id, case_id, datasource_name)
        await self._create_snapshot_node(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            case_id=case_id,
            datasource_name=datasource_name,
            version=next_version,
            trigger_type=trigger_type,
            created_by=created_by,
            description=description,
        )

        try:
            # 3. 읽기 전용 트랜잭션으로 서브그래프 수집
            subgraph = await self.store.read_datasource_subgraph(
                tenant_id, case_id, datasource_name
            )
            fk_relations = await self.store.read_fk_relations(
                tenant_id, case_id, datasource_name
            )
            tags = await self.store.read_tags(
                tenant_id, case_id, datasource_name
            )

            # 4. JSON 직렬화 (orjson -- 빠르고 메모리 효율적)
            graph_data = self._serialize_graph_data(
                datasource=ds,
                subgraph=subgraph,
                foreign_keys=fk_relations,
                tags=tags,
            )
            graph_json = orjson.dumps(graph_data).decode("utf-8")
            size_bytes = len(graph_json.encode("utf-8"))

            # 5. 스냅샷 노드 완료 업데이트
            await self._complete_snapshot(snapshot_id, graph_json, size_bytes)

            # 6. Redis 이벤트 발행
            await self.redis.publish("axiom:metadata_changes", {
                "event": "metadata.snapshot.created",
                "tenant_id": tenant_id,
                "case_id": case_id,
                "datasource_name": datasource_name,
                "snapshot_id": snapshot_id,
                "version": next_version,
                "trigger_type": trigger_type,
            })

            # 7. 보존 정책 (초과 스냅샷 정리)
            await self._enforce_retention(tenant_id, case_id, datasource_name)

            elapsed_ms = int((time.monotonic() - start) * 1000)

            return {
                "snapshot_id": snapshot_id,
                "version": next_version,
                "status": "completed",
                "size_bytes": size_bytes,
                "duration_ms": elapsed_ms,
            }

        except Exception as e:
            # 실패 시 status를 "failed"로 업데이트
            await self._fail_snapshot(snapshot_id, str(e))
            raise

    def _serialize_graph_data(self, datasource, subgraph, foreign_keys, tags) -> dict:
        """Neo4j 조회 결과를 graph_data 포맷으로 변환"""
        schemas = []
        total_tables = 0
        total_columns = 0

        for schema_data in subgraph:
            tables = []
            for table_data in schema_data["tables"]:
                columns = [
                    {
                        "name": col["name"],
                        "dtype": col["dtype"],
                        "nullable": col["nullable"],
                        "is_primary_key": col.get("is_primary_key", False),
                        "default_value": col.get("default_value"),
                        "description": col.get("description"),
                    }
                    for col in table_data["columns"]
                ]
                tables.append({
                    "name": table_data["name"],
                    "description": table_data.get("description"),
                    "row_count": table_data.get("row_count"),
                    "table_type": table_data.get("table_type"),
                    "columns": columns,
                })
                total_columns += len(columns)
            schemas.append({"name": schema_data["name"], "tables": tables})
            total_tables += len(tables)

        fk_list = [
            {
                "source_schema": fk["source_schema"],
                "source_table": fk["source_table"],
                "source_column": fk["source_column"],
                "target_schema": fk["target_schema"],
                "target_table": fk["target_table"],
                "target_column": fk["target_column"],
                "constraint_name": fk.get("constraint_name"),
            }
            for fk in foreign_keys
        ]

        return {
            "version": "2.0",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "datasource": {
                "name": datasource["name"],
                "engine": datasource["engine"],
                "host": datasource.get("host"),
                "port": datasource.get("port"),
                "database": datasource.get("database"),
                "user": datasource.get("user"),
                "last_extracted": datasource.get("last_extracted"),
            },
            "schemas": schemas,
            "foreign_keys": fk_list,
            "tags": tags or {},
            "statistics": {
                "total_schemas": len(schemas),
                "total_tables": total_tables,
                "total_columns": total_columns,
                "total_fks": len(fk_list),
                "total_tagged_items": len(tags) if tags else 0,
            },
        }
```

### 3.4 비동기 처리

스냅샷 생성은 **백그라운드 태스크**로 실행된다. API 호출자는 즉시 `202 Accepted` 응답을 받고, 스냅샷 상태를 폴링하거나 Redis Stream 이벤트를 구독하여 완료를 확인한다.

```python
# app/api/metadata.py (라우터)
from fastapi import BackgroundTasks

@router.post("/{datasource_name}/snapshots", status_code=202)
async def create_snapshot(
    datasource_name: str,
    body: SnapshotCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_auth),
):
    """패브릭 스냅샷 생성 (비동기)

    즉시 snapshot_id를 반환하고, 백그라운드에서 생성 진행.
    상태 확인: GET /{datasource_name}/snapshots/{snapshot_id}
    """
    snapshot_id = str(uuid.uuid4())

    background_tasks.add_task(
        snapshot_service.create_snapshot,
        tenant_id=current_user.tenant_id,
        case_id=body.case_id,
        datasource_name=datasource_name,
        trigger_type="manual",
        created_by=current_user.email,
        description=body.description,
    )

    return {
        "snapshot_id": snapshot_id,
        "status": "creating",
        "message": "스냅샷 생성이 시작되었습니다. 상태를 폴링하거나 Redis Stream 이벤트를 확인하세요.",
    }
```

### 3.5 성능 고려

| 항목 | 설계 결정 | 근거 |
|------|-----------|------|
| **읽기 전용 트랜잭션** | 메타데이터 수집 시 `READ` 트랜잭션 사용 | 쓰기 잠금 없음. 다른 메타데이터 쿼리를 차단하지 않음 |
| **Python 직렬화** | JSON 직렬화를 Python(orjson)에서 수행 | Neo4j Cypher 내 `apoc.convert.toJson`은 대규모 그래프에서 메모리 압박 유발 |
| **단일 쿼리 수집** | 서브그래프 전체를 1~2개 Cypher 쿼리로 수집 | 다수 소규모 쿼리보다 네트워크 왕복 최소화 |
| **비동기 실행** | FastAPI `BackgroundTasks` 또는 Celery 워커 | API 응답 지연 방지 |
| **orjson** | 표준 `json` 대신 `orjson` 사용 | 2-10배 빠른 직렬화. 메모리 효율적 |

**예상 소요 시간**:

| 데이터소스 규모 | 테이블 수 | 컬럼 수 | 예상 시간 | graph_data 크기 |
|---------------|-----------|---------|-----------|----------------|
| 소규모 | ~20 | ~100 | < 0.5초 | ~15 KB |
| 중규모 | ~100 | ~700 | ~1-2초 | ~70 KB |
| 대규모 | ~500 | ~3,500 | ~3-5초 | ~350 KB |
| 초대규모 | ~1,000 | ~7,000 | ~5-10초 | ~700 KB |

---

## 4. 스냅샷 Diff 알고리즘

### 4.1 Diff 카테고리

| 카테고리 | 설명 | 매칭 기준 |
|----------|------|-----------|
| `tables_added` | 새로 추가된 테이블 | target에만 존재하는 (schema, table) |
| `tables_removed` | 삭제된 테이블 | base에만 존재하는 (schema, table) |
| `columns_added` | 기존 테이블에 추가된 컬럼 | 양쪽에 존재하는 테이블에서 target에만 있는 컬럼 |
| `columns_removed` | 기존 테이블에서 삭제된 컬럼 | 양쪽에 존재하는 테이블에서 base에만 있는 컬럼 |
| `columns_modified` | 속성이 변경된 컬럼 | 동일 (schema, table, column)에서 dtype/nullable/default 변경 |
| `fks_added` | 새로 추가된 FK 관계 | target에만 존재하는 (src_table.src_col -> tgt_table.tgt_col) |
| `fks_removed` | 삭제된 FK 관계 | base에만 존재하는 FK |
| `descriptions_changed` | 설명이 변경된 테이블/컬럼 | 동일 항목에서 description 필드 값 차이 |
| `tags_changed` | 태그가 변경된 항목 | 동일 경로에서 tags 배열 차이 |

### 4.2 Diff 알고리즘

```python
# app/services/snapshot_diff.py
from typing import Any


def compute_snapshot_diff(base_graph: dict, target_graph: dict) -> dict:
    """두 graph_data JSON을 비교하여 diff 결과를 생성한다.

    매칭 전략:
      - 테이블: (schema_name, table_name) 쌍으로 매칭
      - 컬럼: (schema_name, table_name, column_name) 트리플로 매칭
      - FK: (src_schema.src_table.src_column -> tgt_schema.tgt_table.tgt_column) 문자열로 매칭
      - 태그: 경로 문자열로 매칭
    """

    # ── 1단계: 테이블 인덱스 구축 ──
    base_tables = _build_table_index(base_graph["schemas"])
    target_tables = _build_table_index(target_graph["schemas"])

    base_keys = set(base_tables.keys())
    target_keys = set(target_tables.keys())

    tables_added_keys = target_keys - base_keys
    tables_removed_keys = base_keys - target_keys
    tables_common_keys = base_keys & target_keys

    # ── 2단계: 공통 테이블 내 컬럼 비교 ──
    columns_added = []
    columns_removed = []
    columns_modified = []
    descriptions_changed = []

    for tkey in sorted(tables_common_keys):
        bt = base_tables[tkey]
        tt = target_tables[tkey]

        # 테이블 설명 변경 확인
        if bt["description"] != tt["description"]:
            descriptions_changed.append({
                "path": f"{tkey[0]}.{tkey[1]}",
                "type": "table",
                "from": bt["description"],
                "to": tt["description"],
            })

        # 컬럼 비교
        base_cols = {c["name"]: c for c in bt["columns"]}
        target_cols = {c["name"]: c for c in tt["columns"]}

        for col_name in sorted(set(target_cols) - set(base_cols)):
            tc = target_cols[col_name]
            columns_added.append({
                "schema": tkey[0], "table": tkey[1],
                "column": col_name, "dtype": tc["dtype"],
                "nullable": tc["nullable"],
            })

        for col_name in sorted(set(base_cols) - set(target_cols)):
            bc = base_cols[col_name]
            columns_removed.append({
                "schema": tkey[0], "table": tkey[1],
                "column": col_name, "dtype": bc["dtype"],
            })

        for col_name in sorted(set(base_cols) & set(target_cols)):
            bc = base_cols[col_name]
            tc = target_cols[col_name]
            changes = _compare_column_props(bc, tc)
            if changes:
                columns_modified.append({
                    "schema": tkey[0], "table": tkey[1],
                    "column": col_name, "changes": changes,
                })
            # 컬럼 설명 변경
            if bc.get("description") != tc.get("description"):
                descriptions_changed.append({
                    "path": f"{tkey[0]}.{tkey[1]}.{col_name}",
                    "type": "column",
                    "from": bc.get("description"),
                    "to": tc.get("description"),
                })

    # ── 3단계: FK 비교 ──
    base_fks = _build_fk_index(base_graph.get("foreign_keys", []))
    target_fks = _build_fk_index(target_graph.get("foreign_keys", []))

    fks_added = [target_fks[k] for k in sorted(set(target_fks) - set(base_fks))]
    fks_removed = [base_fks[k] for k in sorted(set(base_fks) - set(target_fks))]

    # ── 4단계: 태그 비교 ──
    base_tags = base_graph.get("tags", {})
    target_tags = target_graph.get("tags", {})
    tags_changed = _compare_tags(base_tags, target_tags)

    # ── 결과 조합 ──
    tables_added = [
        {
            "schema": k[0], "table": k[1],
            "column_count": len(target_tables[k]["columns"]),
            "columns": [c["name"] for c in target_tables[k]["columns"]],
        }
        for k in sorted(tables_added_keys)
    ]
    tables_removed = [
        {
            "schema": k[0], "table": k[1],
            "column_count": len(base_tables[k]["columns"]),
        }
        for k in sorted(tables_removed_keys)
    ]

    return {
        "base_version": base_graph.get("_version"),
        "target_version": target_graph.get("_version"),
        "base_captured_at": base_graph["captured_at"],
        "target_captured_at": target_graph["captured_at"],
        "summary": {
            "tables_added": len(tables_added),
            "tables_removed": len(tables_removed),
            "columns_added": len(columns_added),
            "columns_removed": len(columns_removed),
            "columns_modified": len(columns_modified),
            "fks_added": len(fks_added),
            "fks_removed": len(fks_removed),
            "descriptions_changed": len(descriptions_changed),
            "tags_changed": len(tags_changed),
        },
        "details": {
            "tables_added": tables_added,
            "tables_removed": tables_removed,
            "columns_added": columns_added,
            "columns_removed": columns_removed,
            "columns_modified": columns_modified,
            "fks_added": fks_added,
            "fks_removed": fks_removed,
            "descriptions_changed": descriptions_changed,
            "tags_changed": tags_changed,
        },
    }


def _build_table_index(schemas: list[dict]) -> dict[tuple, dict]:
    """(schema_name, table_name) -> table_data 인덱스 구축"""
    index = {}
    for schema in schemas:
        for table in schema["tables"]:
            key = (schema["name"], table["name"])
            index[key] = table
    return index


def _build_fk_index(foreign_keys: list[dict]) -> dict[str, dict]:
    """FK를 고유 문자열 키로 인덱싱"""
    index = {}
    for fk in foreign_keys:
        key = (
            f"{fk['source_schema']}.{fk['source_table']}.{fk['source_column']}"
            f"->"
            f"{fk['target_schema']}.{fk['target_table']}.{fk['target_column']}"
        )
        index[key] = fk
    return index


def _compare_column_props(base_col: dict, target_col: dict) -> dict:
    """컬럼 속성 변경 감지 (description 제외 -- 별도 추적)"""
    changes = {}
    for prop in ("dtype", "nullable", "is_primary_key", "default_value"):
        bv = base_col.get(prop)
        tv = target_col.get(prop)
        if bv != tv:
            changes[prop] = {"from": bv, "to": tv}
    return changes


def _compare_tags(base_tags: dict, target_tags: dict) -> list[dict]:
    """태그 변경 추적"""
    all_paths = set(base_tags.keys()) | set(target_tags.keys())
    changed = []
    for path in sorted(all_paths):
        bt = sorted(base_tags.get(path, []))
        tt = sorted(target_tags.get(path, []))
        if bt != tt:
            changed.append({"path": path, "from": bt, "to": tt})
    return changed
```

### 4.3 Diff API 흐름

```
GET /api/v1/metadata/{datasource}/snapshots/diff?base={version}&target={version}
         │
         ▼
┌─ 1. 캐시 확인 ─────────────────────────────────────────────────┐
│                                                                  │
│  MATCH (d:SnapshotDiff {                                        │
│      tenant_id: $tid, case_id: $cid,                            │
│      datasource_name: $ds,                                      │
│      base_snapshot_id: $base_id,                                │
│      target_snapshot_id: $target_id                             │
│  })                                                              │
│  RETURN d.diff_data                                              │
│                                                                  │
│  → 캐시 히트: 즉시 반환                                          │
│  → 캐시 미스: 계산 진행                                          │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │ 캐시 미스
             ▼
┌─ 2. 양쪽 스냅샷 graph_data 로드 ─────────────────────────────────┐
│                                                                  │
│  MATCH (fs:FabricSnapshot {snapshot_id: $base_id})              │
│  RETURN fs.graph_data                                            │
│  (+ target도 동일하게)                                            │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─ 3. Python에서 diff 계산 ────────────────────────────────────────┐
│                                                                  │
│  base_graph = orjson.loads(base_snapshot.graph_data)             │
│  target_graph = orjson.loads(target_snapshot.graph_data)         │
│  diff_result = compute_snapshot_diff(base_graph, target_graph)  │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─ 4. 캐시 저장 + 반환 ───────────────────────────────────────────┐
│                                                                  │
│  :SnapshotDiff 노드 생성 (재사용 가능)                            │
│  diff_result JSON 반환                                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. 스냅샷 복원

### 5.1 복원 흐름

복원(restore)은 선택한 스냅샷의 `graph_data`를 기반으로 현재 메타데이터 서브그래프를 **완전히 교체**하는 작업이다.

```
POST /api/v1/metadata/{datasource}/snapshots/{snapshot_id}/restore
         │
         ▼
┌─ 1. 권한 확인 ───────────────────────────────────────────────────┐
│                                                                  │
│  require_role("admin")                                           │
│  # 복원은 관리자 권한 필수                                        │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─ 2. 복원 대상 스냅샷 검증 ───────────────────────────────────────┐
│                                                                  │
│  MATCH (fs:FabricSnapshot {                                      │
│      snapshot_id: $snapshot_id,                                  │
│      tenant_id: $tid,                                            │
│      case_id: $cid,                                              │
│      status: "completed"                                         │
│  })                                                              │
│  RETURN fs                                                       │
│                                                                  │
│  → 존재하지 않으면 404                                            │
│  → status != "completed" 이면 400                                │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─ 3. 현재 상태 안전망 스냅샷 자동 생성 ───────────────────────────┐
│                                                                  │
│  await create_snapshot(                                           │
│      trigger_type="auto",                                        │
│      description="복원 전 자동 안전망 스냅샷 (restore safety net)"│
│  )                                                               │
│  # 복원 실패 시 이 스냅샷으로 되돌릴 수 있는 안전망               │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─ 4. 현재 메타데이터 서브그래프 삭제 ──────────────────────────────┐
│                                                                  │
│  Cypher (쓰기 트랜잭션):                                         │
│                                                                  │
│  MATCH (ds:DataSource {                                          │
│      name: $ds_name, tenant_id: $tid, case_id: $cid             │
│  })-[:HAS_SCHEMA]->(s:Schema)-[:HAS_TABLE]->(t:Table)           │
│    -[:HAS_COLUMN]->(c:Column)                                   │
│  DETACH DELETE c                                                 │
│                                                                  │
│  MATCH (ds:DataSource {                                          │
│      name: $ds_name, tenant_id: $tid, case_id: $cid             │
│  })-[:HAS_SCHEMA]->(s:Schema)-[:HAS_TABLE]->(t:Table)           │
│  DETACH DELETE t                                                 │
│                                                                  │
│  MATCH (ds:DataSource {                                          │
│      name: $ds_name, tenant_id: $tid, case_id: $cid             │
│  })-[:HAS_SCHEMA]->(s:Schema)                                   │
│  DETACH DELETE s                                                 │
│                                                                  │
│  # :DataSource 노드 자체는 유지 (connection 정보 보존)            │
│  # :FabricSnapshot 노드들도 유지 (스냅샷 이력 보존)               │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─ 5. 스냅샷 graph_data에서 서브그래프 재생성 ──────────────────────┐
│                                                                  │
│  graph = orjson.loads(snapshot.graph_data)                        │
│                                                                  │
│  # DataSource 속성 업데이트                                       │
│  MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid,          │
│                         case_id: $cid})                          │
│  SET ds.engine = $engine,                                        │
│      ds.last_extracted = datetime($last_extracted)               │
│                                                                  │
│  # Schema 노드 재생성                                            │
│  UNWIND $schemas as schema                                       │
│  MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid,          │
│                         case_id: $cid})                          │
│  CREATE (s:Schema {name: schema.name})                           │
│  CREATE (ds)-[:HAS_SCHEMA]->(s)                                  │
│                                                                  │
│  # Table 노드 배치 생성                                          │
│  UNWIND $tables as tbl                                           │
│  MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid,          │
│          case_id: $cid})-[:HAS_SCHEMA]->(s:Schema {name: tbl.schema})│
│  CREATE (t:Table {                                               │
│      name: tbl.name, description: tbl.description,               │
│      row_count: tbl.row_count, table_type: tbl.table_type        │
│  })                                                              │
│  CREATE (s)-[:HAS_TABLE]->(t)                                    │
│                                                                  │
│  # Column 노드 배치 생성                                         │
│  UNWIND $columns as col                                          │
│  MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid,          │
│          case_id: $cid})                                         │
│      -[:HAS_SCHEMA]->(s:Schema {name: col.schema})               │
│      -[:HAS_TABLE]->(t:Table {name: col.table})                  │
│  CREATE (c:Column {                                              │
│      name: col.name, dtype: col.dtype,                           │
│      nullable: col.nullable, description: col.description,       │
│      is_primary_key: col.is_primary_key,                         │
│      default_value: col.default_value                            │
│  })                                                              │
│  CREATE (t)-[:HAS_COLUMN]->(c)                                   │
│                                                                  │
│  # FK 관계 배치 재생성                                            │
│  UNWIND $fks as fk                                               │
│  MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid,          │
│          case_id: $cid})                                         │
│      -[:HAS_SCHEMA]->(ss:Schema {name: fk.source_schema})        │
│      -[:HAS_TABLE]->(st:Table {name: fk.source_table})           │
│      -[:HAS_COLUMN]->(sc:Column {name: fk.source_column})        │
│  MATCH (ds)                                                      │
│      -[:HAS_SCHEMA]->(ts:Schema {name: fk.target_schema})        │
│      -[:HAS_TABLE]->(tt:Table {name: fk.target_table})           │
│      -[:HAS_COLUMN]->(tc:Column {name: fk.target_column})        │
│  CREATE (sc)-[:FK_TO]->(tc)                                      │
│  CREATE (st)-[:FK_TO_TABLE]->(tt)                                │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─ 6. Redis Stream 이벤트 발행 ─────────────────────────────────────┐
│                                                                  │
│  XADD axiom:metadata_changes * \                                 │
│      event "metadata.snapshot.restored" \                         │
│      tenant_id $tid \                                            │
│      case_id $cid \                                              │
│      datasource_name $ds_name \                                  │
│      snapshot_id $snapshot_id \                                  │
│      version $restored_version \                                 │
│      restored_by $user_email                                     │
│                                                                  │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ▼
┌─ 7. 하류 모듈 자동 전파 ──────────────────────────────────────────┐
│                                                                  │
│  Redis Stream 소비자들이 이벤트를 수신하여 후속 처리:              │
│                                                                  │
│  ┌─ Oracle (NL2SQL) ───────────────────────┐                     │
│  │  - 해당 데이터소스의 캐시된 쿼리 무효화   │                     │
│  │  - 벡터 인덱스 재생성 트리거              │                     │
│  └──────────────────────────────────────────┘                     │
│                                                                  │
│  ┌─ Synapse (온톨로지) ────────────────────┐                     │
│  │  - 온톨로지-메타데이터 링크 재검증        │                     │
│  └──────────────────────────────────────────┘                     │
│                                                                  │
│  ┌─ Canvas (UI) ───────────────────────────┐                     │
│  │  - SSE push: 메타데이터 브라우저 새로고침  │                     │
│  │  - 알림 토스트: "메타데이터가 v5로 복원됨" │                     │
│  └──────────────────────────────────────────┘                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 복원 주의사항

| 항목 | 설명 |
|------|------|
| **실제 DB 스키마는 변경되지 않음** | 원본 DB(PostgreSQL 등)의 테이블 구조는 전혀 변경되지 않는다. 오직 Neo4j의 메타데이터 그래프만 복원된다. 따라서 복원 후 원본 DB와 메타데이터 간에 불일치가 발생할 수 있다. |
| **Oracle 벡터 인덱스 재생성** | 복원 이벤트를 수신한 Oracle 모듈이 해당 데이터소스의 임베딩 벡터를 자동 재생성한다. 이 과정은 비동기이며 수분 소요될 수 있다. |
| **복원 전 안전망 스냅샷** | 복원 직전에 현재 상태를 자동 스냅샷한다. "복원을 되돌리기"가 가능하다. |
| **admin 권한 필수** | `require_role("admin")`. 일반 사용자는 스냅샷 조회/비교만 가능하다. |
| **동시 복원 금지** | 동일 데이터소스에 대해 동시에 복원을 실행할 수 없다. 두 번째 요청은 `409 Conflict`를 반환한다. |
| **MindsDB 상태 불변** | 복원은 Neo4j 메타데이터만 대상이다. MindsDB의 `CREATE DATABASE` 상태는 변경하지 않는다. |

### 5.3 복원 후 전파 다이어그램

```
                     metadata.snapshot.restored 이벤트
                                │
          ┌─────────────────────┼─────────────────────────┐
          │                     │                          │
          ▼                     ▼                          ▼
┌─── Oracle ────────┐ ┌─── Synapse ────────┐ ┌─── Canvas ─────────┐
│                   │ │                     │ │                     │
│ 1. 쿼리 캐시     │ │ 1. 온톨로지         │ │ 1. SSE push:       │
│    무효화         │ │    메타데이터 링크   │ │    metadata_changed │
│                   │ │    재검증            │ │                     │
│ 2. 벡터 인덱스   │ │                     │ │ 2. UI 자동 새로고침 │
│    재생성         │ │ 2. 매핑 불일치       │ │    (메타데이터      │
│    (비동기 ~2분)  │ │    경고 생성         │ │     브라우저)       │
│                   │ │                     │ │                     │
│ 3. NL2SQL         │ │                     │ │ 3. 토스트 알림      │
│    컨텍스트       │ │                     │ │    "erp_db 메타데이터│
│    재로드          │ │                     │ │     v5로 복원됨"    │
│                   │ │                     │ │                     │
└───────────────────┘ └─────────────────────┘ └─────────────────────┘
```

---

## 6. 보존 정책

### 6.1 기본 정책

| 항목 | 기본값 | 설명 |
|------|--------|------|
| **최대 스냅샷 수** | 30 (per datasource) | 데이터소스 당 최대 보존 스냅샷 수 |
| **잠긴 스냅샷 제외** | `is_locked = true`인 스냅샷은 자동 삭제 대상에서 제외 | 감사/규정 준수용 |
| **테넌트별 설정** | 테넌트 설정에서 `max_snapshots_per_datasource` 변경 가능 | 10~100 범위 |
| **수동 생성 스냅샷** | 자동 삭제 대상에 포함 (잠그지 않은 경우) | 잠금으로 보호 가능 |

### 6.2 자동 정리

스냅샷 생성 완료 후 `_enforce_retention` 함수가 실행된다.

```python
async def _enforce_retention(
    self,
    tenant_id: str,
    case_id: str,
    datasource_name: str,
):
    """보존 정책에 따라 초과 스냅샷 자동 삭제

    규칙:
      1. is_locked=true인 스냅샷은 절대 삭제하지 않는다
      2. is_locked=false인 스냅샷만 대상으로 초과분을 삭제한다
      3. 삭제 순서: created_at 오래된 순 (FIFO)
      4. 관련 :SnapshotDiff 노드도 함께 삭제한다
    """
    max_snapshots = await self._get_tenant_max_snapshots(tenant_id)  # 기본: 30

    # 현재 스냅샷 수 조회 (completed 상태만)
    query_count = """
        MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid, case_id: $cid})
            -[:HAS_SNAPSHOT]->(fs:FabricSnapshot {status: "completed"})
        RETURN count(fs) as total,
               count(CASE WHEN fs.is_locked = false THEN 1 END) as unlocked
    """
    result = await self.store.neo4j.execute_query(query_count, {
        "ds_name": datasource_name, "tid": tenant_id, "cid": case_id,
    })
    total = result[0]["total"]
    unlocked = result[0]["unlocked"]

    if total <= max_snapshots:
        return  # 초과 없음

    excess = total - max_snapshots

    if excess <= 0 or unlocked == 0:
        return  # 삭제할 잠기지 않은 스냅샷 없음

    # 오래된 순으로 잠기지 않은 스냅샷 삭제
    delete_count = min(excess, unlocked)

    query_delete = """
        MATCH (ds:DataSource {name: $ds_name, tenant_id: $tid, case_id: $cid})
            -[:HAS_SNAPSHOT]->(fs:FabricSnapshot {status: "completed", is_locked: false})
        WITH fs ORDER BY fs.created_at ASC LIMIT $limit
        // 연결된 SnapshotDiff도 삭제
        OPTIONAL MATCH (fs)-[:DIFF_BASE|DIFF_TARGET]->(d:SnapshotDiff)
        DETACH DELETE d
        WITH fs
        DETACH DELETE fs
        RETURN count(fs) as deleted
    """
    result = await self.store.neo4j.execute_write(query_delete, {
        "ds_name": datasource_name, "tid": tenant_id, "cid": case_id,
        "limit": delete_count,
    })

    deleted = result[0]["deleted"] if result else 0
    if deleted > 0:
        logger.info(
            f"보존 정책 적용: {datasource_name}에서 {deleted}개 스냅샷 삭제 "
            f"(현재 {total - deleted}/{max_snapshots})"
        )
```

### 6.3 스냅샷 잠금 (Lock)

감사 또는 규정 준수 목적으로 특정 스냅샷을 잠글 수 있다.

```
PUT /api/v1/metadata/{datasource}/snapshots/{snapshot_id}/lock
Body: { "is_locked": true, "reason": "2025 회계연도 감사용" }
```

```cypher
MATCH (fs:FabricSnapshot {snapshot_id: $sid, tenant_id: $tid})
SET fs.is_locked = $is_locked
```

잠긴 스냅샷은:
- 보존 정책에 의한 자동 삭제에서 제외
- 수동 삭제 시 `is_locked: true` 경고 + 확인 필요 (`force=true` 파라미터)

### 6.4 스토리지 추정

| 데이터소스 규모 | 테이블 수 | graph_data 크기 | 30개 스냅샷 | 비고 |
|---------------|-----------|----------------|------------|------|
| 소규모 | 20 | ~15 KB | ~450 KB | 무시 가능 |
| 중규모 | 100 | ~70 KB | ~2.1 MB | 무시 가능 |
| 대규모 | 500 | ~350 KB | ~10.5 MB | Neo4j 관점에서 경미 |
| 초대규모 | 1,000 | ~700 KB | ~21 MB | 모니터링 권장 |

**Neo4j 스토리지 관점**: 테넌트 10개, 각 5개 데이터소스(중규모), 30개 스냅샷 기준 약 **105 MB**. Neo4j가 처리하기에 충분히 작은 규모이다.

---

## 7. 멀티테넌트 격리

### 7.1 스냅샷은 테넌트에 귀속

모든 스냅샷 노드는 `tenant_id`와 `case_id`를 필수 속성으로 갖는다. Cypher 쿼리에서 항상 테넌트 필터를 포함해야 한다.

```
┌─ Tenant A (tenant_id: "t-aaa") ──────────────────────────────────────┐
│                                                                       │
│  ┌─ Case 1 (case_id: "c-111") ──────────────────────────────────┐   │
│  │                                                                │   │
│  │  (:DataSource {name: "erp_db"})                               │   │
│  │      │ :HAS_SNAPSHOT                                          │   │
│  │      ├── (:FabricSnapshot {version: 1, tenant_id: "t-aaa"})  │   │
│  │      ├── (:FabricSnapshot {version: 2, tenant_id: "t-aaa"})  │   │
│  │      └── (:FabricSnapshot {version: 3, tenant_id: "t-aaa"})  │   │
│  │                                                                │   │
│  │  (:DataSource {name: "finance_db"})                           │   │
│  │      │ :HAS_SNAPSHOT                                          │   │
│  │      ├── (:FabricSnapshot {version: 1, tenant_id: "t-aaa"})  │   │
│  │      └── (:FabricSnapshot {version: 2, tenant_id: "t-aaa"})  │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─ Case 2 (case_id: "c-222") ──────────────────────────────────┐   │
│  │                                                                │   │
│  │  (:DataSource {name: "erp_db"})  ← Case 1과 동일 이름 가능    │   │
│  │      │ :HAS_SNAPSHOT                                          │   │
│  │      └── (:FabricSnapshot {version: 1, tenant_id: "t-aaa"})  │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘

┌─ Tenant B (tenant_id: "t-bbb") ──────────────────────────────────────┐
│                                                                       │
│  ┌─ Case 3 (case_id: "c-333") ──────────────────────────────────┐   │
│  │                                                                │   │
│  │  (:DataSource {name: "erp_db"})  ← Tenant A와 동일 이름 가능  │   │
│  │      │ :HAS_SNAPSHOT                                          │   │
│  │      └── (:FabricSnapshot {version: 1, tenant_id: "t-bbb"})  │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### 7.2 격리 보장 메커니즘

**모든 쿼리에 tenant_id 필터 필수**:

```cypher
-- 올바른 쿼리 (테넌트 필터 포함)
MATCH (fs:FabricSnapshot {
    tenant_id: $tid,
    case_id: $cid,
    datasource_name: $ds_name
})
RETURN fs ORDER BY fs.version DESC

-- 금지: 테넌트 필터 없는 쿼리
-- MATCH (fs:FabricSnapshot {datasource_name: $ds_name})  ← 절대 사용 금지
```

**서비스 계층에서 강제**:

```python
# 모든 스냅샷 서비스 메서드에 tenant_id 필수
class SnapshotService:
    async def list_snapshots(
        self,
        tenant_id: str,     # JWT에서 추출 -- 사용자가 변조 불가
        case_id: str,
        datasource_name: str,
    ) -> list[dict]:
        # tenant_id는 항상 Cypher 파라미터로 전달
        ...
```

### 7.3 스냅샷 ID 체계

| ID | 범위 | 생성 방식 | 예시 |
|----|------|-----------|------|
| `snapshot_id` | 글로벌 유일 | UUID v4 | `550e8400-e29b-41d4-a716-446655440000` |
| `version` | 데이터소스 내 순차 | auto-increment | 1, 2, 3, ... |

- `snapshot_id`는 UUID이므로 테넌트 간 충돌이 불가능하다
- `version`은 `(tenant_id, case_id, datasource_name)` 범위 내에서만 순차 증가한다
- 외부 API에서는 `snapshot_id`(UUID)를 사용하고, 사용자 친화적 표시에는 `version`을 사용한다

---

## 8. Redis Stream 이벤트

### 8.1 스냅샷 관련 이벤트

**스트림 이름**: `axiom:metadata_changes`

| 이벤트 | 발행 시점 | 소비자 |
|--------|-----------|--------|
| `metadata.snapshot.created` | 스냅샷 생성 완료 시 | Canvas (UI 알림), Oracle (캐시 갱신 검토) |
| `metadata.snapshot.restored` | 스냅샷 복원 완료 시 | Oracle (벡터 재생성), Synapse (링크 재검증), Canvas (UI 새로고침) |
| `metadata.snapshot.deleted` | 스냅샷 삭제 시 | Canvas (목록 갱신) |

### 8.2 이벤트 페이로드 상세

**metadata.snapshot.created**:

```json
{
  "event": "metadata.snapshot.created",
  "tenant_id": "t-001-uuid",
  "case_id": "c-001-uuid",
  "datasource_name": "erp_db",
  "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
  "version": 7,
  "trigger_type": "auto",
  "created_by": "system",
  "statistics": {
    "total_tables": 45,
    "total_columns": 312,
    "total_fks": 28
  },
  "timestamp": "2026-02-20T10:00:00Z"
}
```

**metadata.snapshot.restored**:

```json
{
  "event": "metadata.snapshot.restored",
  "tenant_id": "t-001-uuid",
  "case_id": "c-001-uuid",
  "datasource_name": "erp_db",
  "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
  "version": 5,
  "restored_by": "admin@axiom.kr",
  "safety_snapshot_id": "661f9511-f39c-52e5-b827-557766551111",
  "safety_snapshot_version": 8,
  "timestamp": "2026-02-20T11:30:00Z"
}
```

**metadata.snapshot.deleted**:

```json
{
  "event": "metadata.snapshot.deleted",
  "tenant_id": "t-001-uuid",
  "case_id": "c-001-uuid",
  "datasource_name": "erp_db",
  "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
  "version": 2,
  "deleted_by": "system",
  "reason": "retention_policy",
  "timestamp": "2026-02-20T10:00:01Z"
}
```

### 8.3 Redis 발행 구현

```python
# app/events/redis_publisher.py
import redis.asyncio as redis
import orjson


class RedisPublisher:
    """Redis Stream 이벤트 발행"""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def publish(self, stream: str, payload: dict):
        """Redis Stream에 이벤트 발행

        XADD로 메시지 추가. Stream이 없으면 자동 생성.
        maxlen으로 스트림 크기 제한 (최근 10,000개 유지).
        """
        # orjson으로 중첩 dict를 문자열로 직렬화
        flat_payload = {}
        for k, v in payload.items():
            if isinstance(v, (dict, list)):
                flat_payload[k] = orjson.dumps(v).decode("utf-8")
            else:
                flat_payload[k] = str(v)

        await self.redis.xadd(
            stream,
            flat_payload,
            maxlen=10000,     # 스트림 최대 크기 제한
            approximate=True,  # 성능 최적화 (정확한 maxlen 대신 근사값)
        )
```

---

## 9. API 엔드포인트 요약

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `POST` | `/api/v1/metadata/{datasource}/snapshots` | 스냅샷 생성 | `datasource:write` |
| `GET` | `/api/v1/metadata/{datasource}/snapshots` | 스냅샷 목록 조회 | `datasource:read` |
| `GET` | `/api/v1/metadata/{datasource}/snapshots/{snapshot_id}` | 스냅샷 상세 조회 | `datasource:read` |
| `GET` | `/api/v1/metadata/{datasource}/snapshots/diff` | 두 스냅샷 비교 | `datasource:read` |
| `POST` | `/api/v1/metadata/{datasource}/snapshots/{snapshot_id}/restore` | 스냅샷 복원 | `admin` |
| `PUT` | `/api/v1/metadata/{datasource}/snapshots/{snapshot_id}/lock` | 스냅샷 잠금/해제 | `datasource:write` |
| `DELETE` | `/api/v1/metadata/{datasource}/snapshots/{snapshot_id}` | 스냅샷 삭제 | `datasource:delete` |

---

## 10. 엣지 케이스와 실패 처리

| 상황 | 처리 |
|------|------|
| 스냅샷 생성 중 Neo4j 연결 끊김 | `status: "failed"` 로 업데이트. 불완전 `graph_data`는 빈 문자열로 유지 |
| 복원 중 중간 실패 (삭제 후 재생성 전) | 안전망 스냅샷이 존재하므로 해당 스냅샷으로 재복원 가능. 수동 개입 필요 |
| 동시에 두 사용자가 동일 DS에 스냅샷 생성 | 첫 번째 요청만 성공, 두 번째는 `409 Conflict` |
| graph_data JSON이 Neo4j 문자열 크기 제한 초과 | Neo4j 문자열 한계는 수 GB. 현실적으로 발생 불가 (1,000 테이블 기준 ~700KB) |
| 스냅샷 복원 후 extract-metadata 재실행 | 정상 동작. 복원된 메타데이터를 다시 실제 DB 기준으로 덮어씀 |
| 삭제된 DataSource에 대한 스냅샷 조회 | `:DataSource` 노드가 삭제되면 `:HAS_SNAPSHOT` 관계도 끊어짐. 고아 스냅샷 정리 배치 태스크 필요 |
| graph_data 포맷 버전 불일치 (v1.0 스냅샷을 v2.0에서 읽기) | 마이그레이션 함수 적용. `version` 필드로 분기 처리 |

---

## 11. 관련 문서

| 문서 | 설명 |
|------|------|
| `01_architecture/architecture-overview.md` | Weaver 전체 아키텍처 |
| `01_architecture/data-fabric.md` | 데이터 패브릭 설계 |
| `02_api/metadata-api.md` | 메타데이터 추출 API (스냅샷 자동 트리거 연동) |
| `03_backend/neo4j-metadata.md` | Neo4j 메타데이터 CRUD (서브그래프 읽기/쓰기) |
| `06_data/neo4j-schema.md` | Neo4j 그래프 스키마 (`:FabricSnapshot` 노드 추가 필요) |
| `07_security/connection-security.md` | 보안 정책 (스냅샷의 비밀번호 미포함 원칙) |
| `06_data/data-flow.md` | 데이터 흐름 (스냅샷 생명주기 추가 필요) |
