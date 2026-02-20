# 메타데이터 서비스 아키텍처

<!-- affects: api, backend, data, security -->
<!-- requires-update: 06_data/neo4j-schema.md, 02_api/metadata-api.md -->

> Reference
> - `docs/architecture-semantic-layer.md`
> - `docs/legacy-data-isolation-policy.md`

## 이 문서가 답하는 질문

- Weaver 메타데이터 서비스의 전체 책임 범위는?
- 멀티테넌트 메타데이터 격리는 어떻게 동작하는가?
- 패브릭 스냅샷이란 무엇이고 어떻게 활용하는가?
- Oracle/Synapse/Vision은 메타데이터를 어떻게 소비하는가?
- 메타데이터 변경 전파는 어떻게 이루어지는가?

---

## 1. 메타데이터 서비스 개요

### 1.1 역할 확장

Weaver는 기존 "Data Fabric(MindsDB 게이트웨이 + 메타데이터 그래프)" 역할에서 **"Data Fabric + Metadata Service"**로 승격된다. 전체 Axiom 플랫폼의 스키마 메타데이터에 대한 **Single Source of Truth(SSOT)**를 담당한다.

**Before (현행): 메타데이터 분산 문제**

```
┌─ Weaver ──────────────────┐  ┌─ Oracle ──────────────────┐
│  Neo4j:                    │  │  Neo4j:                    │
│  :DataSource               │  │  :Table (중복!)            │
│  :Schema                   │  │  :Column (중복!)           │
│  :Table                    │  │  :Query                    │
│  :Column                   │  │  :ValueMapping             │
│  :FK_TO                    │  │  vector 인덱스              │
│                            │  │                            │
│  문제: tenant_id 없음      │  │  문제: datasource_id만 있음 │
│  문제: 스냅샷 없음         │  │  문제: Weaver와 스키마 불일치│
└────────────────────────────┘  └────────────────────────────┘

┌─ Synapse ─────────────────┐
│  Neo4j:                    │
│  :Table (중복!)            │
│  :Column (중복!)           │
│  :Query (중복!)            │
│  :ValueMapping (중복!)     │
│  + 4계층 온톨로지          │
│                            │
│  문제: K-AIR 이식 노드 중복│
│  문제: case_id/org_id만 있음│
└────────────────────────────┘
```

**After (목표): Weaver가 메타데이터 SSOT**

```
┌─ Weaver (Metadata SSOT) ──────────────────────────────────┐
│  Neo4j:                                                     │
│  :DataSource {tenant_id, case_id, ...}                      │
│  :Schema     {tenant_id, case_id, ...}                      │
│  :Table      {tenant_id, case_id, ...}  ← vector 속성 포함  │
│  :Column     {tenant_id, case_id, ...}  ← vector 속성 포함  │
│  :FK_TO / :FK_TO_TABLE                                      │
│  :FabricSnapshot                        ← 신규             │
│  :GlossaryTerm                          ← Planned          │
│                                                             │
│  책임: 스키마 추출, LLM 보강, 스냅샷, 변경 전파              │
└──────────┬──────────────┬──────────────┬────────────────────┘
           │              │              │
    Redis Stream    Redis Stream    Redis Stream
    (변경 이벤트)   (변경 이벤트)   (변경 이벤트)
           │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────┐
    │   Oracle    │ │  Synapse   │ │  Vision   │
    │             │ │            │ │           │
    │ :Query      │ │ 4계층 온톨 │ │ OLAP 큐브 │
    │ :ValueMap   │ │ :Resource  │ │ 분석 참조 │
    │ vector검색  │ │ :Process   │ │           │
    │             │ │ :Measure   │ │           │
    │ Table/Col   │ │ :KPI       │ │           │
    │ 노드 제거!  │ │ Table/Col  │ │           │
    │ Weaver 참조 │ │ 노드 제거! │ │           │
    └─────────────┘ └────────────┘ └───────────┘
```

### 1.2 책임 범위

Weaver 메타데이터 서비스는 5가지 핵심 책임(Pillar)을 갖는다.

| Pillar | 설명 | 상태 |
|--------|------|------|
| **Schema SSOT** | DataSource/Schema/Table/Column/FK 노드의 유일한 소유자 | 기존 확장 |
| **Metadata Enrichment** | LLM 기반 테이블/컬럼 설명 생성, 벡터 임베딩 | 기존 확장 |
| **Fabric Snapshot** | 데이터소스별 메타데이터 그래프의 시점 포착 및 Diff | **신규** |
| **Change Propagation** | 메타데이터 변경 시 Redis Stream 이벤트로 소비자 알림 | **신규** |
| **Business Glossary** | 테넌트별 비즈니스 용어 사전 (중앙화) | **Planned (Experimental Spec)** |

### 1.3 소비자-생산자 관계

```
                         ┌───────────────────────────┐
                         │    Weaver Metadata Service │
                         │         (생산자)           │
                         │                           │
                         │  Schema SSOT              │
                         │  Fabric Snapshot          │
                         │  Metadata Enrichment      │
                         │  Change Propagation       │
                         └─────┬─────┬─────┬─────────┘
                               │     │     │
                   ┌───────────┘     │     └───────────┐
                   │                 │                   │
            ┌──────▼──────┐  ┌──────▼──────┐  ┌────────▼──────┐
            │   Oracle    │  │   Synapse   │  │    Vision     │
            │  (소비자)   │  │  (소비자)   │  │   (소비자)    │
            └─────────────┘  └─────────────┘  └───────────────┘
```

**소비자별 메타데이터 사용 목적:**

| 소비자 | 읽는 데이터 | 목적 | 접근 방식 |
|--------|------------|------|----------|
| **Oracle** | Table/Column + vector, FK 관계, description | NL2SQL 컨텍스트 구성, 벡터 검색으로 관련 테이블 탐색 | Weaver API 또는 공유 Neo4j 읽기 |
| **Synapse** | Table/Column 구조, FK 관계 | 온톨로지-스키마 매핑, Process Mining 이벤트 로그 바인딩 | Weaver API |
| **Vision** | Table/Column 구조, datasource 정보 | OLAP 큐브 정의 대상 테이블 탐색, ETL 파이프라인 참조 | Weaver API |
| **Canvas** | 전체 메타데이터 트리 | 메타데이터 브라우저 UI, 스키마 탐색기 렌더링 | Weaver REST API + SSE |

---

## 2. 멀티테넌트 메타데이터 격리

### 2.1 스코핑 계층

Axiom 메타데이터는 다음 계층 구조를 따른다. 이는 플랫폼의 비즈니스 모델을 직접 반영한다.

```
tenant (Axiom 플랫폼 고객, 예: "김앤장 법률사무소")
  │
  ├── case (프로젝트/사건, 예: "삼성전자 M&A 분석 2026")
  │     │
  │     ├── datasource (연결된 DB, 예: "samsung_erp_db")
  │     │     │
  │     │     ├── schema (예: "public")
  │     │     │     │
  │     │     │     ├── table (예: "processes")
  │     │     │     │     │
  │     │     │     │     ├── column (예: "process_code")
  │     │     │     │     ├── column (예: "org_id")
  │     │     │     │     └── ...
  │     │     │     │
  │     │     │     └── table (예: "organizations")
  │     │     │           └── ...
  │     │     │
  │     │     └── schema (예: "accounting")
  │     │           └── ...
  │     │
  │     └── datasource (예: "samsung_finance_db")
  │           └── ...
  │
  └── case (예: "LG전자 실사 2026-Q2")
        │
        └── datasource (예: "lg_erp_db")
              └── ...
```

**핵심 규칙:**

- `tenant_id`는 JWT에서 추출한다 (Core ADR-003 ContextVar 패턴).
- `case_id`는 프로젝트/사건 단위 스코프이다 (Synapse가 이미 `case_id` + `org_id` 패턴 사용).
- DataSource는 `(name, tenant_id, case_id)` 조합이 유일하다 -- **name만으로는 유일하지 않다**.
- 서로 다른 테넌트가 동일한 이름의 datasource를 가질 수 있다 (예: 두 테넌트 모두 "erp_db" 사용).
- 서로 다른 case가 동일한 이름의 datasource를 가질 수 있다.

### 2.2 Neo4j 테넌트 격리 전략

**현행 문제 (변경 전):** 기존 Neo4j 스키마에 `tenant_id`와 `case_id`가 없다. DataSource의 UNIQUE 제약이 `name`에만 걸려 있어, 서로 다른 테넌트/케이스의 동명 datasource를 구분할 수 없다. §2.1의 목표 규칙(`(name, tenant_id, case_id)` 복합 유일성)을 달성하기 위해 아래와 같이 변경한다.

**변경 사항:**

모든 메타데이터 노드에 `tenant_id`를 추가한다. DataSource 이하 노드에는 `case_id`도 추가한다.

```cypher
-- BEFORE: 테넌트 미분리
(:DataSource {
    name: "erp_db",             -- UNIQUE (name만)
    engine: "postgresql",
    ...
})

-- AFTER: 테넌트 격리
(:DataSource {
    name: "erp_db",
    tenant_id: "tenant-uuid-001",   -- NOT NULL, 신규
    case_id: "case-uuid-042",       -- NOT NULL, 신규
    engine: "postgresql",
    ...
})
```

**제약조건 변경:**

```cypher
-- BEFORE
CREATE CONSTRAINT ds_name_unique IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.name IS UNIQUE;

-- AFTER: (name, tenant_id, case_id) 복합 유일 제약
DROP CONSTRAINT ds_name_unique IF EXISTS;

CREATE CONSTRAINT ds_tenant_case_name_unique IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE (ds.name, ds.tenant_id, ds.case_id) IS UNIQUE;

-- NOT NULL 제약
CREATE CONSTRAINT ds_tenant_id_not_null IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.tenant_id IS NOT NULL;

CREATE CONSTRAINT ds_case_id_not_null IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.case_id IS NOT NULL;
```

**인덱스 전략:**

테넌트 스코프 쿼리 성능을 위한 복합 인덱스를 추가한다.

```cypher
-- 테넌트별 DataSource 목록 조회 (가장 빈번한 쿼리)
CREATE INDEX ds_tenant_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id);

-- 테넌트+케이스별 DataSource 조회
CREATE INDEX ds_tenant_case_idx IF NOT EXISTS
    FOR (ds:DataSource) ON (ds.tenant_id, ds.case_id);

-- 하위 노드에도 tenant_id 인덱스 (크로스 체크 용도)
CREATE INDEX table_tenant_idx IF NOT EXISTS
    FOR (t:Table) ON (t.tenant_id);

CREATE INDEX column_tenant_idx IF NOT EXISTS
    FOR (c:Column) ON (c.tenant_id);
```

**하위 노드의 tenant_id:**

Schema, Table, Column 노드에도 `tenant_id`와 `case_id`를 저장한다. 그래프 탐색 없이 단일 노드 레벨에서 테넌트 필터링을 가능하게 하기 위함이다 (Defense-in-Depth).

```cypher
(:Table {
    name: "processes",
    tenant_id: "tenant-uuid-001",   -- DataSource로부터 전파
    case_id: "case-uuid-042",       -- DataSource로부터 전파
    description: "비즈니스 프로세스 정보",
    row_count: 15420,
    table_type: "BASE TABLE"
})
```

**근거:** Neo4j는 PostgreSQL RLS와 같은 내장 행 수준 보안이 없다. 모든 노드에 `tenant_id`를 저장하고 모든 Cypher 쿼리에 테넌트 필터를 적용하여 격리를 구현한다.

### 2.3 API 레벨 격리

JWT에서 추출한 `tenant_id`가 모든 Neo4j 쿼리의 스코프로 사용된다. 크로스 테넌트 데이터 유출을 방지하는 구조는 다음과 같다.

```python
# app/core/middleware.py (Core ADR-003 패턴 적용)
from contextvars import ContextVar

tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
case_id_var: ContextVar[str] = ContextVar("case_id", default="")

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token_data = request.state.token_data  # JWT 미들웨어에서 설정
        tenant_id_var.set(token_data["tenant_id"])
        # case_id는 경로 파라미터 또는 쿼리 파라미터에서 추출
        case_id = request.path_params.get("case_id") or \
                  request.query_params.get("case_id")
        if case_id:
            case_id_var.set(case_id)
        response = await call_next(request)
        return response
```

```python
# app/neo4j/metadata_store.py - 모든 쿼리에 tenant_id 주입
class MetadataStore:
    async def get_datasources(self, tenant_id: str, case_id: str) -> list:
        """테넌트+케이스 스코프의 DataSource 목록 조회"""
        query = """
            MATCH (ds:DataSource {tenant_id: $tenant_id, case_id: $case_id})
            RETURN ds
            ORDER BY ds.name
        """
        return await self.neo4j.execute_query(query, {
            "tenant_id": tenant_id,
            "case_id": case_id,
        })

    async def get_datasource_metadata(
        self, tenant_id: str, case_id: str, datasource_name: str
    ) -> dict:
        """테넌트 스코프 메타데이터 조회 -- tenant_id 없이 조회 불가"""
        query = """
            MATCH (ds:DataSource {
                name: $name,
                tenant_id: $tenant_id,
                case_id: $case_id
            })
            -[:HAS_SCHEMA]->(s:Schema)
            -[:HAS_TABLE]->(t:Table)
            -[:HAS_COLUMN]->(c:Column)
            RETURN ds, s, t, collect(c) as columns
        """
        return await self.neo4j.execute_query(query, {
            "name": datasource_name,
            "tenant_id": tenant_id,
            "case_id": case_id,
        })
```

**금지사항:**

- `tenant_id` 없이 Neo4j 쿼리를 실행하지 않는다.
- `tenant_id`를 사용자 입력(쿼리 파라미터, 요청 바디)에서 받지 않는다 -- JWT에서만 추출한다.
- Admin API를 제외하고 크로스 테넌트 쿼리를 허용하지 않는다.

### 2.4 격리 레벨 비교

Core의 4중 격리 모델(ADR-003)과 Weaver의 대응 관계:

```
Core (PostgreSQL)                    Weaver (Neo4j)
=====================                =====================

Layer 1: JWT 검증                    Layer 1: JWT 검증
  → tenant_id 추출                     → tenant_id 추출
  → 위조 불가 (서명 검증)               → 동일

Layer 2: ContextVar                  Layer 2: ContextVar
  → 요청 스코프에 tenant_id 격리        → 동일 패턴 적용
  → asyncio 태스크 간 간섭 없음         → 동일

Layer 3: PostgreSQL RLS              Layer 3: Neo4j Query Scope
  → DB 레벨에서 자동 필터링             → 모든 Cypher에 tenant_id 조건
  → SET app.current_tenant_id          → MATCH 절에 tenant_id 파라미터
  → 개발자 실수 방지                    → MetadataStore가 강제 적용

Layer 4: 명시적 WHERE                Layer 4: Label Filter (향후)
  → ORM 쿼리에 tenant_id 조건          → Neo4j Multi-tenancy Label 전략
  → 코드 가독성 + 디버깅               → (향후 Neo4j Enterprise의
                                          Fine-grained Access Control)
```

**차이점:** PostgreSQL은 RLS가 DB 엔진 레벨에서 자동으로 필터링하지만, Neo4j는 그러한 기능이 없다. 따라서 Layer 3를 MetadataStore 클래스에서 **모든 public 메서드가 tenant_id를 필수 파라미터로 받도록** 강제하여 보완한다. tenant_id 없이 호출할 수 있는 메서드는 존재하지 않는다.

---

## 3. 패브릭 스냅샷

### 3.1 스냅샷 개념

**패브릭 스냅샷(Fabric Snapshot)**은 특정 시점의 데이터소스 메타데이터 그래프 상태를 포착한 불변(immutable) 기록이다.

**중요:** 스냅샷은 **실제 데이터의 백업이 아니다**. 오직 Weaver가 인식하는 스키마 구조(테이블, 컬럼, FK, 설명)의 시점 사본이다.

**활용 시나리오:**

| 시나리오 | 설명 |
|---------|------|
| 스키마 마이그레이션 추적 | "ERP DB 마이그레이션 전후 스키마가 어떻게 바뀌었나?" |
| 감사 추적 | "2026년 1월 시점의 거래 테이블 구조는 어떠했나?" |
| 롤백 | "잘못된 메타데이터 추출을 이전 상태로 되돌리고 싶다" |
| 변경 영향 분석 | "지난주 대비 어떤 테이블/컬럼이 추가/삭제되었나?" |
| 규정 준수 | "데이터 구조 변경 이력을 감사인에게 제출해야 한다" |

### 3.2 스냅샷 모델

스냅샷은 Neo4j 노드로 저장되되, 상세 내용은 직렬화된 JSON으로 보관한다. 개별 TableSnapshot/ColumnSnapshot 노드를 만들지 않는 이유는 스냅샷 데이터는 읽기 전용이며 그래프 탐색이 불필요하기 때문이다.

```cypher
(:FabricSnapshot {
    id: "snap-uuid-001",               -- UNIQUE, UUID
    tenant_id: "tenant-uuid-001",       -- NOT NULL
    case_id: "case-uuid-042",           -- NOT NULL
    datasource_name: "erp_db",          -- NOT NULL
    version: 3,                         -- Integer, 자동 증분 (해당 DS 기준)
    created_at: datetime(),             -- 생성 시각
    created_by: "user-uuid-007",        -- 생성자
    trigger_type: "post_extraction",    -- manual | post_extraction | scheduled
    status: "completed",                -- pending | completed | failed
    summary: {                          -- Map (요약 통계)
        schemas: 3,
        tables: 25,
        columns: 150,
        foreign_keys: 18
    },
    graph_data: "{ ... }",             -- String (직렬화된 전체 메타데이터 JSON)
    parent_snapshot_id: "snap-uuid-000" -- 이전 스냅샷 참조 (nullable, 최초 시 null)
})
```

**관계:**

```cypher
(:DataSource)-[:HAS_SNAPSHOT]->(:FabricSnapshot)
(:FabricSnapshot)-[:PREVIOUS]->(:FabricSnapshot)  -- 버전 체인
```

**graph_data JSON 형식:**

```json
{
  "datasource": {
    "name": "erp_db",
    "engine": "postgresql",
    "last_extracted": "2026-02-20T10:00:00Z"
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
              "description": "프로세스 고유 ID"
            },
            {
              "name": "org_id",
              "dtype": "bigint",
              "nullable": false,
              "is_primary_key": false,
              "description": "대상 조직 ID (FK)"
            }
          ],
          "foreign_keys": [
            {
              "source_column": "org_id",
              "target_schema": "public",
              "target_table": "organizations",
              "target_column": "id"
            }
          ]
        }
      ]
    }
  ],
  "snapshot_metadata": {
    "version": 3,
    "captured_at": "2026-02-20T10:05:00Z",
    "graph_node_count": 176,
    "graph_relationship_count": 169
  }
}
```

### 3.3 스냅샷 생성 흐름

```
                    스냅샷 트리거
                        │
            ┌───────────┼───────────┐
            │           │           │
       ┌────▼────┐ ┌────▼────┐ ┌───▼──────┐
       │ 수동    │ │ 추출 후 │ │ 스케줄   │
       │ (API)  │ │ (자동)  │ │ (Airflow)│
       └────┬────┘ └────┬────┘ └────┬─────┘
            │           │           │
            └───────────┼───────────┘
                        │
                        ▼
         ┌─ 스냅샷 생성 프로세스 ─────────────────────┐
         │                                              │
         │  1. FabricSnapshot 노드 생성                 │
         │     status = "pending"                       │
         │     version = (이전 최대 버전 + 1)           │
         │                                              │
         │  2. DataSource 서브그래프 직렬화              │
         │     MATCH (ds)-[:HAS_SCHEMA]->(s)            │
         │           -[:HAS_TABLE]->(t)                 │
         │           -[:HAS_COLUMN]->(c)                │
         │     + FK 관계 수집                            │
         │     → JSON 직렬화                             │
         │                                              │
         │  3. graph_data에 JSON 저장                    │
         │     summary 통계 계산                         │
         │     status = "completed"                     │
         │                                              │
         │  4. PREVIOUS 관계 연결                        │
         │     (현재 스냅샷) -[:PREVIOUS]-> (이전 스냅샷) │
         │                                              │
         │  5. Redis Stream 이벤트 발행                  │
         │     axiom:metadata_changes                    │
         │     event: "snapshot.created"                 │
         │                                              │
         └──────────────────────────────────────────────┘
```

**구현 (Cypher + Python 의사코드):**

```python
class SnapshotService:
    async def create_snapshot(
        self,
        tenant_id: str,
        case_id: str,
        datasource_name: str,
        trigger_type: str,  # "manual" | "post_extraction" | "scheduled"
        created_by: str,
    ) -> dict:
        # 1. 현재 메타데이터 그래프 직렬화
        graph_data = await self._serialize_datasource_graph(
            tenant_id, case_id, datasource_name
        )

        # 2. 버전 번호 결정
        latest_version = await self._get_latest_version(
            tenant_id, case_id, datasource_name
        )
        new_version = (latest_version or 0) + 1

        # 3. FabricSnapshot 노드 생성
        snapshot_id = str(uuid4())
        await self.neo4j.execute_write("""
            MATCH (ds:DataSource {
                name: $ds_name,
                tenant_id: $tenant_id,
                case_id: $case_id
            })
            CREATE (snap:FabricSnapshot {
                id: $snap_id,
                tenant_id: $tenant_id,
                case_id: $case_id,
                datasource_name: $ds_name,
                version: $version,
                created_at: datetime(),
                created_by: $created_by,
                trigger_type: $trigger_type,
                status: "completed",
                summary: $summary,
                graph_data: $graph_data
            })
            CREATE (ds)-[:HAS_SNAPSHOT]->(snap)
        """, { ... })

        # 4. PREVIOUS 체인 연결
        if latest_version:
            await self._link_previous_snapshot(
                tenant_id, case_id, datasource_name,
                new_version, latest_version
            )

        # 5. Redis Stream 이벤트 발행
        await self.event_bus.publish("axiom:metadata_changes", {
            "event": "snapshot.created",
            "tenant_id": tenant_id,
            "case_id": case_id,
            "datasource_name": datasource_name,
            "snapshot_id": snapshot_id,
            "version": new_version,
            "trigger_type": trigger_type,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return {"snapshot_id": snapshot_id, "version": new_version}
```

**자동 스냅샷 (post-extraction):**

메타데이터 추출(`POST /api/datasources/{name}/extract-metadata`) 완료 시, 자동으로 스냅샷을 생성한다. 이를 통해 모든 추출 이력이 기록된다.

```python
# extract-metadata 엔드포인트의 마지막 단계
async def _post_extraction_hook(self, tenant_id, case_id, datasource_name):
    """추출 완료 후 자동 스냅샷 생성"""
    await self.snapshot_service.create_snapshot(
        tenant_id=tenant_id,
        case_id=case_id,
        datasource_name=datasource_name,
        trigger_type="post_extraction",
        created_by="system",
    )
```

### 3.4 스냅샷 Diff

두 스냅샷 간의 메타데이터 변경 사항을 비교한다.

```python
class SnapshotDiffService:
    async def diff(
        self,
        tenant_id: str,
        case_id: str,
        datasource_name: str,
        version_from: int,
        version_to: int,
    ) -> dict:
        """두 스냅샷 간 Diff 계산

        Returns:
            {
                "from_version": 2,
                "to_version": 3,
                "tables": {
                    "added": ["new_audit_log"],
                    "removed": ["deprecated_metrics"],
                    "modified": [
                        {
                            "name": "processes",
                            "columns_added": ["approved_by", "approved_at"],
                            "columns_removed": [],
                            "columns_modified": [
                                {
                                    "name": "process_status",
                                    "changes": {
                                        "dtype": {"from": "varchar(20)",
                                                  "to": "varchar(30)"}
                                    }
                                }
                            ],
                            "description_changed": true,
                            "row_count_changed": {
                                "from": 15420,
                                "to": 16891
                            }
                        }
                    ]
                },
                "foreign_keys": {
                    "added": [
                        {"source": "processes.approved_by",
                         "target": "users.id"}
                    ],
                    "removed": []
                },
                "summary": {
                    "tables_added": 1,
                    "tables_removed": 1,
                    "tables_modified": 1,
                    "columns_added": 2,
                    "columns_removed": 0,
                    "columns_modified": 1,
                    "fks_added": 1,
                    "fks_removed": 0
                }
            }
        """
        snap_from = await self._load_snapshot(
            tenant_id, case_id, datasource_name, version_from
        )
        snap_to = await self._load_snapshot(
            tenant_id, case_id, datasource_name, version_to
        )

        return self._compute_diff(snap_from, snap_to)
```

### 3.5 스냅샷 복원

메타데이터 그래프를 이전 스냅샷 상태로 되돌린다.

```
┌─ 복원 프로세스 ─────────────────────────────────────────────┐
│                                                               │
│  1. 대상 스냅샷의 graph_data 로드                             │
│  2. 현재 메타데이터 스냅샷 자동 생성 (복원 전 백업)           │
│     trigger_type = "pre_restore_backup"                      │
│  3. 현재 DataSource 하위 메타데이터 삭제                      │
│  4. 스냅샷의 graph_data를 Neo4j 노드/관계로 복원              │
│  5. DataSource.last_extracted를 스냅샷 시점으로 설정           │
│  6. Redis Stream 이벤트 발행: "snapshot.restored"              │
│     → Oracle: 벡터 인덱스 재구축                              │
│     → Synapse: 온톨로지-메타데이터 링크 갱신                  │
│                                                               │
│  주의: 실제 데이터베이스는 변경되지 않는다!                    │
│  복원은 Weaver의 "인식(view)"만 되돌리는 것이다.              │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**주의사항:**

- 복원 후 실제 DB 스키마와 Weaver 메타데이터가 불일치할 수 있다. 복원은 "의도적으로 과거 상태를 참조" 하거나 "잘못된 추출을 되돌리기" 위한 것이다.
- 복원 시 반드시 현재 상태를 먼저 스냅샷으로 보존한다 (되돌리기의 되돌리기 지원).
- 복원 후 Oracle/Synapse에 `snapshot.restored` 이벤트를 전파하여 캐시 무효화 및 재동기화를 트리거한다.

### 3.6 보존 정책

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `max_snapshots_per_datasource` | 30 | 데이터소스당 최대 스냅샷 수 |
| `min_retention_days` | 90 | 최소 보존 기간 (일) |
| `auto_cleanup_enabled` | true | 자동 정리 활성화 |
| `exclude_trigger_types` | `["manual"]` | 자동 정리에서 제외할 트리거 유형 |

**정리 규칙:**

```
1. max_snapshots_per_datasource 초과 시 오래된 스냅샷부터 삭제
2. 단, min_retention_days 이내의 스냅샷은 삭제하지 않음
3. manual 트리거로 생성된 스냅샷은 자동 삭제하지 않음
4. pre_restore_backup 스냅샷은 min_retention_days 이내만 보존
```

**테넌트별 설정 오버라이드:**

```python
# 테넌트별 보존 정책 설정 (향후)
{
    "tenant_id": "tenant-uuid-001",
    "snapshot_retention": {
        "max_snapshots_per_datasource": 50,  # 기본값 오버라이드
        "min_retention_days": 365,           # 1년 보존 (감사 요구)
    }
}
```

---

## 4. 메타데이터 SSOT (Single Source of Truth)

### 4.1 통합 전략

현재 3개 모듈(Weaver, Oracle, Synapse)에 중복 존재하는 스키마 메타데이터 노드를 Weaver에 일원화한다.

**통합 원칙:**

1. **Weaver가 유일한 소유자:** DataSource, Schema, Table, Column, FK 노드는 Weaver만 생성/수정/삭제한다.
2. **Oracle은 보강자:** Weaver의 Table/Column 노드에 `vector` 속성을 추가하고, 자체 :Query/:ValueMapping 노드를 생성한다. Table/Column 노드를 복제하지 않는다.
3. **Synapse는 소비자:** 스키마 메타데이터는 Weaver API로 읽는다. K-AIR에서 이식한 :Table/:Column/:Query/:ValueMapping 중복 노드를 제거하고, 4계층 온톨로지 노드에 집중한다.

**통합 전후 비교 (Oracle):**

```
BEFORE: Oracle이 자체 :Table/:Column 노드 보유
  Oracle Neo4j:
    (:Table {name, schema, db, datasource_id, description, vector, ...})
    (:Column {fqn, name, dtype, description, vector, ...})
    (:Query)-[:USES_TABLE]->(:Table)
    (:ValueMapping)-[:MAPPED_VALUE]->(:Column)

AFTER: Oracle은 Weaver의 노드를 참조
  Weaver Neo4j (공유):
    (:Table {name, tenant_id, case_id, description, vector, ...})
    (:Column {name, tenant_id, case_id, dtype, description, vector, ...})

  Oracle Neo4j (자체):
    (:Query {id, question, sql, vector, ...})
    (:Query)-[:USES_TABLE]->(:Table)         -- Weaver의 Table 노드 참조
    (:ValueMapping)-[:MAPPED_VALUE]->(:Column) -- Weaver의 Column 노드 참조
```

### 4.2 노드 소유권 매트릭스

| 노드 레이블 | 소유자 (Write) | 소비자 (Read) | 비고 |
|-------------|---------------|--------------|------|
| `:DataSource` | **Weaver** | Oracle, Synapse, Vision, Canvas | CRUD + tenant 격리 |
| `:Schema` | **Weaver** | Oracle, Synapse, Vision, Canvas | 스키마 인트로스펙션 |
| `:Table` | **Weaver** | Oracle, Synapse, Vision, Canvas | 벡터 속성은 Oracle이 추가 |
| `:Column` | **Weaver** | Oracle, Synapse, Vision, Canvas | 벡터 속성은 Oracle이 추가 |
| `:FabricSnapshot` | **Weaver** | Canvas (UI 표시) | 스냅샷 관리 |
| `:GlossaryTerm` | **Weaver** (Planned) | Oracle, Synapse, Vision | 비즈니스 용어 사전 |
| `:Query` | **Oracle** | Canvas (히스토리 표시) | NL2SQL 캐시 |
| `:ValueMapping` | **Oracle** | -- | 값 매핑 |
| `:Resource` | **Synapse** | Canvas, Vision | 4계층 온톨로지 |
| `:Process` | **Synapse** | Canvas, Vision | 4계층 온톨로지 |
| `:Measure` | **Synapse** | Canvas, Vision | 4계층 온톨로지 |
| `:KPI` | **Synapse** | Canvas, Vision | 4계층 온톨로지 |
| `:EventLog` | **Synapse** | Canvas | Process Mining |
| `:BusinessEvent` | **Synapse** | Canvas | EventStorming |

### 4.3 Vector Index 관리

Oracle은 NL2SQL 벡터 검색을 위해 Table/Column 노드에 임베딩 벡터가 필요하다. 기존에는 Oracle이 자체 :Table/:Column 노드에 `vector` 속성을 저장했으나, SSOT 통합 이후에는 Weaver의 노드에 직접 벡터 속성을 추가한다.

**방식: Weaver 노드에 Oracle이 벡터 속성을 "보강"**

```cypher
-- Oracle이 Weaver의 :Table 노드에 vector 속성 추가
MATCH (t:Table {
    name: $table_name,
    tenant_id: $tenant_id,
    case_id: $case_id
})
SET t.vector = $embedding_vector
```

```cypher
-- 벡터 인덱스는 공유 Neo4j에 생성 (Oracle 부트스트랩 시)
CREATE VECTOR INDEX table_vector IF NOT EXISTS
FOR (t:Table) ON (t.vector)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
};

CREATE VECTOR INDEX column_vector IF NOT EXISTS
FOR (c:Column) ON (c.vector)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
};
```

**자동 재인덱싱 흐름:**

```
Weaver: 메타데이터 추출 완료
    │
    ▼
Redis Stream: axiom:metadata_changes
  event: "schema.extracted"
  data: {tenant_id, case_id, datasource_name, tables_changed: [...]}
    │
    ▼
Oracle Consumer:
  1. 변경된 Table/Column 노드의 description 확인
  2. 새 description이 있으면 임베딩 벡터 재생성
  3. Neo4j의 vector 속성 업데이트
  4. 기존 :Query 노드의 USES_TABLE 관계 재검증
```

---

## 5. 변경 전파 메커니즘

### 5.1 Redis Stream 이벤트

메타데이터 변경 시 Redis Stream `axiom:metadata_changes`에 이벤트를 발행한다. Core ADR-004의 Redis Streams 이벤트 버스 패턴을 따른다.

**Stream 설정:**

```python
METADATA_STREAM_CONFIG = {
    "axiom:metadata_changes": {
        "maxlen": 50_000,
        "consumer_groups": [
            "oracle-metadata-sync",     # Oracle: 벡터 재인덱싱
            "synapse-metadata-sync",    # Synapse: 온톨로지 링크 갱신
            "canvas-metadata-push",     # Canvas: SSE 푸시 알림
        ],
    },
}
```

**이벤트 카탈로그:**

| 이벤트 | 트리거 시점 | 데이터 |
|--------|-----------|--------|
| `schema.extracted` | 메타데이터 추출 완료 | tenant_id, case_id, datasource_name, summary |
| `table.added` | 추출 시 새 테이블 발견 | tenant_id, case_id, datasource_name, table_name |
| `table.removed` | 추출 시 테이블 사라짐 | tenant_id, case_id, datasource_name, table_name |
| `column.modified` | 컬럼 타입/속성 변경 | tenant_id, case_id, datasource_name, table_name, column_name, changes |
| `description.updated` | LLM 보강 또는 수동 수정 | tenant_id, case_id, datasource_name, table_name, column_name |
| `snapshot.created` | 스냅샷 생성 | tenant_id, case_id, datasource_name, snapshot_id, version |
| `snapshot.restored` | 스냅샷 복원 | tenant_id, case_id, datasource_name, restored_version |
| `datasource.deleted` | 데이터소스 삭제 | tenant_id, case_id, datasource_name |

**이벤트 형식:**

```python
# 모든 이벤트에 공통으로 포함되는 필드
{
    "event_id": "evt-uuid-001",              # 멱등성 키
    "event": "schema.extracted",             # 이벤트 타입
    "tenant_id": "tenant-uuid-001",          # 필수
    "case_id": "case-uuid-042",              # 필수
    "datasource_name": "erp_db",             # 필수
    "timestamp": "2026-02-20T10:05:00Z",     # 발행 시각
    "payload": { ... }                       # 이벤트별 상세 데이터
}
```

### 5.2 소비자별 반응

```
┌─ axiom:metadata_changes Stream ──────────────────────────────┐
│                                                               │
│  event: "schema.extracted"                                    │
│  event: "description.updated"                                 │
│  event: "snapshot.restored"                                   │
│  event: "datasource.deleted"                                  │
│  ...                                                          │
└───┬─────────────────┬──────────────────┬─────────────────────┘
    │                 │                  │
    ▼                 ▼                  ▼
┌─ Oracle ───┐  ┌─ Synapse ───┐  ┌─ Canvas ─────────────┐
│             │  │              │  │                       │
│ schema.     │  │ schema.      │  │ schema.extracted      │
│ extracted:  │  │ extracted:   │  │ → SSE push:           │
│ → 벡터 재  │  │ → 온톨로지   │  │   "메타데이터 추출    │
│   인덱싱   │  │   -메타 링크 │  │    완료" 알림         │
│ → 쿼리 캐시│  │   재검증     │  │                       │
│   무효화   │  │              │  │ description.updated   │
│             │  │ description. │  │ → 메타데이터          │
│ description.│  │ updated:     │  │   브라우저 UI 갱신    │
│ updated:   │  │ → NER 사전   │  │                       │
│ → 해당     │  │   갱신       │  │ snapshot.created      │
│   테이블   │  │              │  │ → 스냅샷 히스토리     │
│   벡터 재  │  │ snapshot.    │  │   UI 갱신             │
│   생성     │  │ restored:    │  │                       │
│             │  │ → 전체 재   │  │ datasource.deleted    │
│ datasource.│  │   동기화     │  │ → UI에서 해당         │
│ deleted:   │  │              │  │   DS 제거             │
│ → 해당 DS  │  │ datasource.  │  │                       │
│   Query/VM │  │ deleted:     │  │                       │
│   정리     │  │ → 관련 온톨 │  │                       │
│             │  │   로지 링크 │  │                       │
│             │  │   정리       │  │                       │
└─────────────┘  └──────────────┘  └───────────────────────┘
```

**Oracle의 schema.extracted 처리 상세:**

```python
# Oracle Consumer: oracle-metadata-sync
class OracleMetadataSyncWorker:
    async def handle_schema_extracted(self, event: dict):
        tenant_id = event["tenant_id"]
        case_id = event["case_id"]
        datasource_name = event["datasource_name"]

        # 1. Weaver의 Table/Column 노드에서 description 확인
        tables = await self.neo4j.execute_query("""
            MATCH (ds:DataSource {
                name: $ds_name,
                tenant_id: $tenant_id,
                case_id: $case_id
            })-[:HAS_SCHEMA]->(s)-[:HAS_TABLE]->(t)
            WHERE t.description IS NOT NULL
            RETURN t.name as name, t.description as description
        """, {...})

        # 2. description이 있는 테이블에 대해 임베딩 벡터 생성
        for table in tables:
            vector = await self.embedding_service.embed(table["description"])
            await self.neo4j.execute_write("""
                MATCH (t:Table {
                    name: $name,
                    tenant_id: $tenant_id,
                    case_id: $case_id
                })
                SET t.vector = $vector
            """, {"name": table["name"], "vector": vector, ...})

        # 3. 기존 Query 캐시 중 해당 datasource의 것 무효화
        await self.cache_service.invalidate_queries(
            tenant_id, case_id, datasource_name
        )
```

---

## 6. 비즈니스 용어 사전 (Planned, Experimental Spec)

> 상태 정합성 공지
> - 본 섹션은 "설계/계약 확정" 상태이며, 운영 배포 완료 상태가 아니다.
> - API 계약은 `02_api/metadata-catalog-api.md`에 정의하되, 해당 문서도 `Planned (Experimental)`로 관리한다.

### 6.1 설계 방향

현재 비즈니스 용어는 여러 모듈에 하드코딩되어 있다:

| 위치 | 형태 | 문제 |
|------|------|------|
| Synapse NER | `BUSINESS_TERMS` 딕셔너리 | 코드 변경 없이 용어 추가 불가 |
| Vision 프롬프트 | 인라인 용어 매핑 | 모듈 간 불일치 |
| Oracle ValueMapping | :ValueMapping 노드 | 컬럼 레벨 매핑만 가능, 비즈니스 용어 사전 아님 |

**목표:** Weaver에 테넌트별 비즈니스 용어 사전(:GlossaryTerm)을 중앙화하여, 모든 모듈이 일관된 용어를 사용하게 한다.

**Neo4j 모델 (계획):**

```cypher
(:GlossaryTerm {
    id: "gls-uuid-001",
    tenant_id: "tenant-uuid-001",       -- 테넌트 스코프
    term: "매출액",                      -- 정규 용어
    synonyms: ["매출", "수익", "revenue", "sales"], -- 동의어 목록
    definition: "일정 기간 동안 재화 또는 용역 제공의 대가로 수취한 금액",
    domain: "finance",                   -- 도메인 분류
    related_columns: ["revenue", "total_sales", "sales_amount"], -- 관련 컬럼명 패턴
    created_at: datetime(),
    updated_at: datetime()
})
```

**활용 계획:**

- Oracle NL2SQL: 자연어 질문에서 비즈니스 용어를 인식하고 관련 컬럼을 탐색
- Synapse NER: GlossaryTerm 기반 Named Entity Recognition
- Vision: 분석 결과 설명에 정확한 비즈니스 용어 사용
- Canvas: 용어 사전 관리 UI + 자동완성

**API (계획):**

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/glossary` | 용어 생성 |
| `GET` | `/api/glossary` | 용어 목록 (테넌트 스코프) |
| `GET` | `/api/glossary/search?q={query}` | 용어 검색 (동의어 포함) |
| `PUT` | `/api/glossary/{id}` | 용어 수정 |
| `DELETE` | `/api/glossary/{id}` | 용어 삭제 |

---

## 7. 마이그레이션 계획

기존 Neo4j 스키마에서 새로운 테넌트 격리 스키마로의 전환 계획이다.

### 7.1 단계별 마이그레이션

```
Phase 1: Weaver 스키마 확장 (Breaking Change)
  - 모든 노드에 tenant_id, case_id 속성 추가
  - DataSource UNIQUE 제약 변경: (name) → (name, tenant_id, case_id)
  - FabricSnapshot 노드/관계 스키마 생성
  - 인덱스 추가

Phase 2: Weaver API 확장
  - 모든 API에 tenant_id(JWT) + case_id(path/query) 스코핑 적용
  - 스냅샷 API 추가
  - Redis Stream 이벤트 발행 추가

Phase 3: Oracle 통합
  - Oracle의 :Table/:Column 중복 노드 제거
  - Weaver의 Table/Column에 vector 속성 추가
  - Oracle의 :Query/:ValueMapping이 Weaver 노드를 참조하도록 관계 변경
  - Oracle Consumer Worker 배포

Phase 4: Synapse 통합
  - Synapse의 K-AIR 이식 :Table/:Column/:Query/:ValueMapping 노드 제거
  - 4계층 온톨로지 노드는 유지
  - 온톨로지-메타데이터 간 관계를 Weaver 노드로 연결
  - Synapse Consumer Worker 배포
```

---

## 8. 관련 문서

| 문서 | 위치 | 설명 |
|------|------|------|
| 아키텍처 개요 | `01_architecture/architecture-overview.md` | Weaver 전체 아키텍처 |
| 데이터 패브릭 | `01_architecture/data-fabric.md` | MindsDB 게이트웨이 + 메타데이터 그래프 |
| 어댑터 패턴 | `01_architecture/adapter-pattern.md` | 스키마 인트로스펙션 설계 |
| 메타데이터 추출 API | `02_api/metadata-api.md` | SSE 기반 추출 API 스펙 |
| Neo4j 스키마 | `06_data/neo4j-schema.md` | Neo4j 노드/관계 스키마 (업데이트 필요) |
| Neo4j 메타데이터 CRUD | `03_backend/neo4j-metadata.md` | MetadataStore 구현 (업데이트 필요) |
| LLM 보강 | `05_llm/metadata-enrichment.md` | LLM 기반 description 생성 |
| Core ContextVar | `core/99_decisions/ADR-003-contextvar-multitenancy.md` | 멀티테넌트 격리 패턴 |
| Core Redis Streams | `core/99_decisions/ADR-004-redis-streams-event-bus.md` | 이벤트 버스 아키텍처 |
| Core 데이터 격리 | `core/07_security/data-isolation.md` | 4중 격리 모델 |
| Oracle Neo4j 스키마 | `oracle/06_data/neo4j-schema.md` | Oracle 그래프 스키마 (통합 대상) |
| Synapse Neo4j 스키마 | `synapse/06_data/neo4j-schema.md` | Synapse 그래프 스키마 (통합 대상) |
| ADR-001 MindsDB | `99_decisions/ADR-001-mindsdb-gateway.md` | MindsDB 게이트웨이 선택 근거 |
| ADR-003 Neo4j | `99_decisions/ADR-003-neo4j-metadata.md` | Neo4j 메타데이터 저장소 선택 근거 |
