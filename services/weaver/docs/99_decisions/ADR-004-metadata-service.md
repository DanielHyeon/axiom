# ADR-004: Weaver 메타데이터 서비스 격상

## 상태

Accepted

## 날짜

2026-02-20

## 컨텍스트

Axiom 플랫폼은 현재 3개 모듈(Weaver, Oracle, Synapse)이 **각각 독립적으로 Neo4j에 메타데이터를 관리**하고 있다. 동일한 개념(Table, Column)이 모듈마다 다른 스키마로 중복 정의되어 있으며, 모듈 간 메타데이터 정합성을 보장하는 메커니즘이 없다.

### 문제 1: 동일 데이터의 3중 정의

| 모듈 | Table 노드 스키마 | Column 노드 스키마 | 비고 |
|------|-------------------|-------------------|------|
| **Weaver** | `name, description, row_count, table_type` | `name, dtype, nullable, description, is_primary_key, default_value` | DataSource→Schema→Table→Column 계층, **tenant_id 없음** |
| **Oracle** | `name, schema, db, datasource_id, description, vector, text_to_sql_is_valid, column_count, row_count_estimate` | `fqn, name, dtype, nullable, is_primary_key, description, vector, datasource_id, sample_values` | 벡터 인덱스 추가, datasource_id로 스코핑 |
| **Synapse** | `name, description, embedding, row_count, sample_data` | `name, table_name, data_type, description, embedding, nullable, is_pk, is_fk` | K-AIR 이식 + 4계층 온톨로지와 공존 |

예를 들어, `erp_db.public.processes` 테이블 하나를 등록하면 Neo4j에 Table 노드가 **3개** 생성될 수 있다. 각 모듈이 서로 다른 속성명(`dtype` vs `data_type`, `is_primary_key` vs `is_pk`)과 서로 다른 벡터 속성명(`vector` vs `embedding`)을 사용하여, 하나의 테이블에 대한 메타데이터가 분산되고 불일치한다.

### 문제 2: 테넌트 격리 부재

Weaver의 현행 Neo4j 스키마에서 DataSource 노드는 `name`에 UNIQUE 제약이 걸려 있다:

```cypher
CREATE CONSTRAINT ds_name_unique IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.name IS UNIQUE;
```

이는 **전역적으로 유일**해야 한다는 의미이다. 고객 A가 `erp_db`라는 이름으로 데이터소스를 등록하면, 고객 B는 같은 이름을 사용할 수 없다. 비즈니스 수준의 멀티 테넌시가 불가능하다.

### 문제 3: 특정 시점 메타데이터 스냅샷 부재

현재 메타데이터 추출(`last_extracted` 타임스탬프)은 있으나, **이전 시점의 스키마 상태를 복원하거나 비교하는 메커니즘이 없다**. 데이터소스의 스키마가 변경되면 기존 메타데이터가 덮어씌워지며:

- "지난달 대비 어떤 테이블/컬럼이 추가/삭제되었는가?" 에 답할 수 없음
- 스키마 변경으로 인한 NL2SQL 장애 발생 시 원인 추적 불가
- 감사(audit) 요구사항 충족 불가

### 문제 4: 중앙화된 비즈니스 용어 사전(Business Glossary) 부재

비즈니스 도메인 용어(예: "매출", "거래처", "원가율")와 DB 컬럼/테이블 간의 매핑이 **프롬프트에 하드코딩**되어 있다. Oracle의 NL2SQL 프롬프트와 Synapse의 엔티티 추출 프롬프트에 각각 별도의 도메인 용어가 산재해 있으며, 이를 수정하려면 코드 배포가 필요하다.

### 문제 5: 모듈 간 메타데이터 변경 전파 부재

Weaver에서 메타데이터를 추출/갱신해도, Oracle의 벡터 인덱스가 자동으로 재생성되지 않고, Synapse의 K-AIR 이식 테이블/컬럼 노드와 동기화되지 않는다. 현재는 각 모듈이 독립적으로 Neo4j에 접근하여 자체 노드를 관리하므로:

- Weaver에서 새 테이블을 발견해도 Oracle이 인지하지 못함
- Oracle에서 벡터 인덱스를 갱신해도 Synapse의 embedding과 동기화 안 됨
- Synapse에서 테이블 설명을 수정해도 Weaver/Oracle에 반영 안 됨

### 문제 6: Oracle 벡터 속성과 Weaver 노드의 관계 모호

Oracle은 Table/Column 노드에 `vector` 속성(1536차원)을 추가하여 벡터 검색을 수행한다. 그러나 이 노드들이 Weaver가 생성한 노드와 **동일 노드인지, 별도 사본인지** 명확하지 않다. Oracle의 `datasource_id` 기반 스코핑과 Weaver의 `DataSource.name` 기반 스코핑이 서로 다른 체계를 사용하여, 조인이나 참조가 불가능하다.

---

## 결정

**Weaver를 "Data Fabric" 전용 모듈에서 "Data Fabric + Metadata Service"로 격상**한다. Weaver가 Axiom 플랫폼의 메타데이터 **Single Source of Truth(SSOT)**가 되어, 다른 모듈은 Weaver가 관리하는 메타데이터를 소비만 한다.

### 핵심 변경 사항

#### 1. 모든 노드에 `tenant_id` 추가

```cypher
-- 변경 전
CREATE CONSTRAINT ds_name_unique IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE ds.name IS UNIQUE;

-- 변경 후
CREATE CONSTRAINT ds_tenant_name_unique IF NOT EXISTS
    FOR (ds:DataSource) REQUIRE (ds.tenant_id, ds.name) IS UNIQUE;
```

`tenant_id`는 Axiom Core에서 발급하는 비즈니스 단위 식별자이다. DataSource, Schema, Table, Column 모든 레벨에 `tenant_id`를 부여하여 테넌트 간 완전 격리를 보장한다. Neo4j Cypher 쿼리 시 항상 `tenant_id`를 필터 조건에 포함한다.

#### 2. Fabric Snapshot (특정 시점 메타데이터 스냅샷)

```cypher
(:FabricSnapshot {
    id: "snap-20260220-001",
    tenant_id: "tenant-abc",
    datasource_name: "erp_db",
    snapshot_type: "full",          -- full / incremental
    created_at: datetime(),
    created_by: "system",           -- system(자동) / user_id(수동)
    schema_hash: "sha256:...",      -- 스키마 구조 해시
    metadata: "{ ... }"             -- 직렬화된 스키마 구조 JSON
})

(:FabricSnapshot)-[:SNAPSHOT_OF]->(:DataSource)
(:FabricSnapshot)-[:DIFF_FROM]->(:FabricSnapshot)  -- 이전 스냅샷과의 차이
```

메타데이터 추출(introspection) 실행 시마다 자동으로 스냅샷을 생성한다. 스냅샷 간 diff를 계산하여 테이블/컬럼 추가/삭제/변경을 추적한다.

#### 3. SSOT 소유권 모델

| 데이터 영역 | 소유 모듈 | 소비 모듈 | 설명 |
|------------|----------|----------|------|
| DataSource, Schema, Table, Column, FK | **Weaver** (쓰기) | Oracle, Synapse (읽기) | 스키마 메타데이터 |
| vector/embedding 속성 | **Weaver** (쓰기) | Oracle, Synapse (읽기) | 벡터 인덱스 통합 관리 |
| Query 캐시 | **Oracle** (쓰기) | Weaver (읽기) | NL2SQL 결과 캐시 |
| ValueMapping | **Oracle** (쓰기) | Synapse (읽기) | 값 매핑은 NL2SQL 도메인 |
| 4계층 온톨로지 (Resource, Process, Measure, KPI) | **Synapse** (쓰기) | Oracle, Vision (읽기) | 비즈니스 도메인 지식 |
| Process Mining (BusinessEvent, EventLog 등) | **Synapse** (쓰기) | Vision (읽기) | 프로세스 마이닝 |
| Business Glossary | **Weaver** (쓰기) | Oracle, Synapse (읽기) | 비즈니스 용어 사전 |

핵심 원칙: **스키마 메타데이터(Table, Column)는 오직 Weaver만 생성/수정/삭제**한다. Oracle과 Synapse는 Weaver가 관리하는 노드를 참조만 하고, 자체적으로 Table/Column 노드를 생성하지 않는다.

#### 4. 메타데이터 변경 전파 (Redis Stream)

```
Weaver: 메타데이터 변경 발생
    │
    ▼
Redis Stream: axiom.metadata.changes
    │
    ├──▶ Oracle: 벡터 인덱스 재생성 트리거
    ├──▶ Synapse: 온톨로지 연결 갱신
    └──▶ Canvas: UI 캐시 무효화
```

메타데이터 변경 이벤트 포맷:

```json
{
    "event_type": "schema_changed",
    "tenant_id": "tenant-abc",
    "datasource": "erp_db",
    "changes": [
        {"type": "table_added", "table": "new_table"},
        {"type": "column_modified", "table": "processes", "column": "status", "field": "dtype"}
    ],
    "snapshot_id": "snap-20260220-001",
    "timestamp": "2026-02-20T10:00:00Z"
}
```

#### 5. Business Glossary

```cypher
(:GlossaryTerm {
    id: "term-001",
    tenant_id: "tenant-abc",
    term: "매출",
    definition: "특정 기간 동안 상품/서비스 판매로 발생한 총 수익",
    synonyms: ["매출액", "매출수익", "revenue", "sales"],
    domain: "finance",
    created_by: "admin",
    created_at: datetime(),
    updated_at: datetime()
})

(:GlossaryTerm)-[:MAPS_TO_TABLE]->(:Table)
(:GlossaryTerm)-[:MAPS_TO_COLUMN]->(:Column)
```

LLM 프롬프트에 하드코딩된 도메인 용어를 GlossaryTerm 노드로 이전한다. Oracle의 NL2SQL과 Synapse의 엔티티 추출이 동일한 용어 사전을 참조하게 된다.

---

## 고려한 대안

### Option A: Weaver 메타데이터 서비스 격상 (선택)

Weaver의 기존 인프라(Neo4j 연결, 어댑터 패턴, MindsDB 통합)를 확장하여 메타데이터 SSOT 역할을 부여한다.

**장점**:
- 기존 Weaver 인프라(Neo4j 클라이언트, 어댑터 패턴, Cypher 쿼리) 재사용 → 개발 비용 최소화
- Weaver가 이미 메타데이터 추출의 시작점(DataSource→Schema→Table→Column) → 자연스러운 확장
- 모듈 수 변경 없음 (6개 유지) → 운영 복잡도 증가 없음
- 기존 `POST /api/datasources/{name}/extract` 엔드포인트를 확장하여 스냅샷/전파 로직 추가 가능

**단점**:
- Weaver의 책임 범위 확대: "데이터 패브릭"에서 "데이터 패브릭 + 메타데이터 서비스"로 → 단일 책임 원칙(SRP) 약화
- Weaver 장애 시 영향 범위 증가: 쿼리 실행 불가 + 메타데이터 서비스 중단
- 기존 Weaver Neo4j 스키마 마이그레이션 필요 (`tenant_id` 추가, 인덱스 재생성)

### Option B: 독립 메타데이터 서비스 신설

새로운 모듈(예: `Atlas` 또는 `Catalog`)을 생성하여 메타데이터 SSOT 전담.

**장점**:
- 깨끗한 관심사 분리: Weaver=패브릭, Atlas=메타데이터
- 독립적 스케일링 가능
- Weaver 장애가 메타데이터 서비스에 영향 없음

**단점**:
- 7번째 모듈 추가 → 인프라/운영/배포 복잡도 증가 (Docker Compose, CI/CD 파이프라인, 모니터링)
- Weaver와 신규 모듈 간 통신 오버헤드 (Weaver가 추출한 메타데이터를 Atlas에 전달하는 이중 경로)
- 현재 Axiom 팀 규모(소규모) 대비 과잉 설계(overengineering) 리스크
- Neo4j 연결이 2개 모듈에서 관리되어야 함 (Weaver의 기존 연결 + Atlas의 새 연결)
- 기존 Oracle/Synapse가 Neo4j에 직접 접근하는 패턴을 Atlas API 호출로 전환하는 비용이 Option A보다 큼

### Option C: 현상 유지 (기각)

각 모듈이 계속 독립적으로 메타데이터를 관리한다.

**기각 사유**:
- 3중 스키마 정의 문제가 모듈 추가(Vision 등)마다 악화
- 멀티 테넌시 지원이 불가능하여 B2B SaaS 전환 자체가 차단됨
- 메타데이터 불일치로 인한 NL2SQL 오류가 이미 관찰됨 (Oracle이 Weaver와 다른 컬럼 타입 정보를 가지는 사례)
- 비즈니스 용어가 프롬프트에 하드코딩되어 고객별 커스터마이징 불가
- 기술 부채가 선형이 아닌 **지수적으로** 증가하는 구조

---

## 결과

### 긍정적 영향

1. **SSOT 확립**: Table/Column 메타데이터가 단일 소유권 모델로 관리되어 모듈 간 불일치 제거
2. **멀티 테넌시**: `tenant_id` 기반 격리로 B2B SaaS 모델 지원 가능
3. **스키마 변경 추적**: Fabric Snapshot으로 특정 시점 스키마 상태 복원/비교 가능, 감사 요구사항 충족
4. **벡터 인덱스 통합**: Weaver가 벡터 속성을 통합 관리하여 속성명(`vector` vs `embedding`) 불일치 제거
5. **변경 전파**: Redis Stream을 통한 비동기 이벤트 전파로 모듈 간 느슨한 결합(loose coupling) 유지
6. **비즈니스 용어 관리**: GlossaryTerm 노드로 프롬프트 하드코딩 탈피, 고객별 용어 사전 커스터마이징 가능
7. **Oracle/Synapse 단순화**: 자체 Table/Column 노드 생성/관리 로직 제거 → 핵심 로직(NL2SQL, 온톨로지)에 집중

### 부정적 영향/리스크

1. **Weaver 책임 범위 과대**: 데이터 패브릭 + 메타데이터 SSOT + 비즈니스 용어 사전 → 향후 분리 필요 가능성 (재평가 조건 참조)
2. **마이그레이션 비용**: 3개 모듈의 Neo4j 스키마를 통합하는 데이터 마이그레이션 필요
   - Weaver: `tenant_id` 추가, UNIQUE 제약 변경
   - Oracle: 자체 Table/Column 노드를 Weaver 노드 참조로 전환, `datasource_id` → `tenant_id + datasource_name` 체계 전환
   - Synapse: K-AIR 이식 Table/Column 노드를 Weaver 노드 참조로 전환
3. **Weaver 가용성 중요도 상승**: 메타데이터 서비스 중단 시 Oracle NL2SQL과 Synapse 엔티티 추출 모두 영향 → 헬스체크/장애 복구 강화 필요
4. **Redis Stream 운영**: 메타데이터 변경 전파를 위한 Redis Stream 인프라 추가 → 이벤트 유실, 순서 보장 등 고려 필요
5. **성능 우려**: 모든 메타데이터 접근이 Weaver를 경유하면 병목 가능 → Neo4j 직접 읽기(read-only)는 허용하되 쓰기만 Weaver 전담으로 설계

### 필요한 변경

| 모듈 | 변경 사항 | 우선순위 | 예상 공수 |
|------|----------|---------|----------|
| **Weaver** | 모든 노드에 `tenant_id` 속성 추가, UNIQUE 제약을 `(tenant_id, name)` 복합으로 변경 | P0 | 2일 |
| **Weaver** | FabricSnapshot 노드/관계 추가, 추출 시 자동 스냅샷 생성 로직 | P0 | 3일 |
| **Weaver** | GlossaryTerm CRUD API 추가 (`POST/GET/PUT/DELETE /api/glossary`) | P1 | 2일 |
| **Weaver** | Redis Stream 발행 로직 (`axiom.metadata.changes` 스트림) | P1 | 2일 |
| **Weaver** | 벡터 임베딩 생성/관리 로직 추가 (기존 Oracle/Synapse에서 이관) | P1 | 3일 |
| **Oracle** | 자체 Table/Column 노드 생성 제거, Weaver 노드 참조로 전환 | P1 | 3일 |
| **Oracle** | `datasource_id` 기반 스코핑을 `tenant_id + datasource_name`으로 전환 | P1 | 2일 |
| **Oracle** | Redis Stream 구독, 메타데이터 변경 시 벡터 재인덱싱 트리거 | P2 | 2일 |
| **Synapse** | K-AIR 이식 Table/Column 노드 제거, Weaver 노드 참조로 전환 | P1 | 3일 |
| **Synapse** | 4계층 온톨로지 노드에 `tenant_id` 추가 | P1 | 2일 |
| **Synapse** | Redis Stream 구독, 메타데이터 변경 시 온톨로지 연결 갱신 | P2 | 2일 |
| **Canvas** | 데이터소스 관리 UI에 테넌트 컨텍스트 반영 | P1 | 1일 |
| **Canvas** | Fabric Snapshot 조회/비교 UI | P2 | 3일 |
| **Canvas** | Business Glossary 관리 UI | P2 | 3일 |
| **Core** | JWT에 `tenant_id` 클레임 포함 보장, 테넌트 미들웨어 | P0 | 1일 |

**총 예상 공수**: ~34일 (1인 기준, 단계적 적용 시 Phase 3~4에 걸쳐 수행)

---

## 재평가 조건

- Weaver의 코드베이스가 10,000줄을 초과하여 단일 모듈로 관리하기 어려운 경우 → Option B(독립 메타데이터 서비스) 재검토
- 테넌트 수가 100개를 초과하여 Neo4j 단일 DB 내 `tenant_id` 파티셔닝으로 성능이 부족한 경우 → 테넌트별 Neo4j 인스턴스 또는 멀티 DB 구성 검토
- Redis Stream의 이벤트 유실/지연이 비즈니스 임팩트를 미치는 경우 → Kafka 등 전용 메시지 브로커 도입 검토
- 메타데이터 서비스 API 호출량이 초당 1000건을 초과하는 경우 → API Gateway 캐싱 또는 독립 서비스 분리 검토

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| `01_architecture/data-fabric.md` | 데이터 패브릭 설계 (현행) |
| `06_data/neo4j-schema.md` | Weaver Neo4j 스키마 (현행) |
| `99_decisions/ADR-003-neo4j-metadata.md` | Neo4j 메타데이터 저장소 선택 근거 |
| Oracle `06_data/neo4j-schema.md` | Oracle Neo4j 스키마 (마이그레이션 대상) |
| Synapse `06_data/neo4j-schema.md` | Synapse Neo4j 스키마 (마이그레이션 대상) |
| K-AIR 역설계 분석 보고서 | 원본 메타데이터 아키텍처 참조 |
