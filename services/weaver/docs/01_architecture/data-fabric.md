# 데이터 패브릭 설계

<!-- affects: api, backend, data, llm -->
<!-- requires-update: 02_api/query-api.md, 06_data/data-flow.md -->

> Reference
> - `docs/architecture-semantic-layer.md`
> - `docs/legacy-data-isolation-policy.md`

## 이 문서가 답하는 질문

- 데이터 패브릭이란 정확히 무엇인가?
- 다중 DB 추상화는 어떻게 동작하는가?
- 메타데이터 그래프는 왜 필요하고, 어떻게 활용되는가?
- 비즈니스 프로세스 인텔리전스에서 데이터 패브릭의 가치는 무엇인가?

---

## 1. 데이터 패브릭 컨셉

### 1.1 정의

데이터 패브릭(Data Fabric)은 **물리적으로 분산된 데이터 소스를 논리적으로 통합하는 아키텍처**이다. 데이터를 한 곳으로 이동(ETL)하는 대신, 데이터가 있는 곳에서 직접 질의하되, 사용자에게는 단일 인터페이스를 제공한다.

### 1.2 Weaver의 데이터 패브릭 = MindsDB + Neo4j

```
┌─ 논리 계층 (Logical Layer) ──────────────────────────────────┐
│                                                               │
│  ┌─ 쿼리 통합 (MindsDB) ──────────────────────────────────┐ │
│  │                                                         │ │
│  │  "SELECT s.name, o.amount                               │ │
│  │   FROM erp_db.stakeholders s                            │ │
│  │   JOIN finance_db.transactions o ON s.id = o.entity_id" │ │
│  │                                                         │ │
│  │  → erp_db는 PostgreSQL, finance_db는 MySQL              │ │
│  │  → MindsDB가 자동으로 분배 실행 후 결과 통합             │ │
│  │                                                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ 메타데이터 그래프 (Neo4j) ─────────────────────────────┐ │
│  │                                                         │ │
│  │  (:DataSource)-[:HAS_SCHEMA]->(:Schema)                 │ │
│  │  (:Schema)-[:HAS_TABLE]->(:Table)                       │ │
│  │  (:Table)-[:HAS_COLUMN]->(:Column)                      │ │
│  │  (:Column)-[:FK_TO]->(:Column)                          │ │
│  │                                                         │ │
│  │  → "erp_db의 stakeholders 테이블은 어떤 컬럼이 있나?"   │ │
│  │  → "finance_db에서 entity_id FK가 어디로 연결되나?"      │ │
│  │                                                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└───────────────────────────────────────────────────────────────┘
                            │
┌─ 물리 계층 (Physical Layer) ─────────────────────────────────┐
│                                                               │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│  │ PG 1   │ │ PG 2   │ │ MySQL  │ │ Oracle │ │ Mongo  │    │
│  │ERP DB  │ │HR DB   │ │재무DB  │ │CRM DB  │ │문서DB  │    │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. 다중 DB 추상화

### 2.1 MindsDB의 역할

MindsDB는 **MySQL 프로토콜 호환 게이트웨이**이다. 내부적으로 각 DB 엔진에 대한 핸들러(Handler)를 가지고 있어, 하나의 SQL 문에서 여러 DB를 참조할 수 있다.

```sql
-- MindsDB에 등록된 데이터소스들
-- erp_db: PostgreSQL (ERP 시스템)
-- finance_db: MySQL (재무 시스템)
-- crm_db: Oracle (CRM)

-- 크로스 DB 조인 쿼리 예시
SELECT
    p.process_id,
    p.org_name,
    f.total_revenue,
    c.customer_count
FROM erp_db.public.processes p
JOIN finance_db.accounting.revenue_summary f ON p.org_id = f.org_id
JOIN crm_db.sales.customer_metrics c ON p.org_id = c.org_id
WHERE p.process_status = 'active';
```

### 2.2 MindsDB 데이터소스 등록

각 외부 DB는 MindsDB에 "데이터베이스"로 등록된다.

```sql
-- PostgreSQL ERP DB 등록
CREATE DATABASE erp_db
ENGINE = 'postgresql'
PARAMETERS = {
    "host": "erp-db.internal",
    "port": 5432,
    "database": "enterprise_ops",
    "user": "reader",
    "password": "***"
};

-- MySQL 재무 시스템 DB 등록
CREATE DATABASE finance_db
ENGINE = 'mysql'
PARAMETERS = {
    "host": "finance-db.internal",
    "port": 3306,
    "database": "accounting",
    "user": "readonly",
    "password": "***"
};
```

### 2.3 엔진별 연결 파라미터

| 엔진 | 필수 파라미터 | 선택 파라미터 |
|------|-------------|-------------|
| **PostgreSQL** | host, port, database, user, password | schema, sslmode |
| **MySQL** | host, port, database, user, password | charset, ssl |
| **Oracle** | host, port, sid/service_name, user, password | encoding |
| **MongoDB** | host, port, database | username, password, auth_source |
| **Redis** | host, port | password, db |
| **Elasticsearch** | hosts | username, password, scheme |
| **Web** | url | - |
| **OpenAI** | api_key | model, max_tokens |

---

## 3. 메타데이터 그래프

### 3.1 왜 메타데이터 그래프가 필요한가

**결정**: 메타데이터를 Neo4j 그래프에 저장한다.

**근거**:
1. **FK 경로 탐색**: "조직 테이블에서 거래 테이블까지 어떤 조인 경로가 있는가?" → 그래프 탐색으로 자동 발견
2. **AI 컨텍스트 제공**: Oracle(NL2SQL) 모듈이 자연어 질의를 SQL로 변환할 때, 테이블/컬럼 관계 정보가 필수
3. **다중 DB 통합 뷰**: 서로 다른 DB의 스키마를 하나의 그래프에서 탐색 가능
4. **설명 보강**: LLM이 생성한 테이블/컬럼 설명을 그래프 노드의 속성으로 저장

### 3.2 그래프 모델

```
(:DataSource {name, engine, host, port, database, user, password})
    │
    │ :HAS_SCHEMA
    ▼
(:Schema {name})
    │
    │ :HAS_TABLE
    ▼
(:Table {name, description})
    │
    │ :HAS_COLUMN
    ▼
(:Column {name, dtype, nullable, description})
    │
    │ :FK_TO (외래 키 관계)
    ▼
(:Column)  ← 다른 테이블의 컬럼

(:Table) -[:FK_TO_TABLE]-> (:Table)  ← 테이블 레벨 FK 요약
```

### 3.3 그래프 활용 시나리오

#### 시나리오 1: FK 경로 탐색

```cypher
-- "조직(organizations) 테이블에서 거래(transactions) 테이블까지 조인 경로는?"
MATCH path = (t1:Table {name: 'organizations'})-[:HAS_COLUMN]->(:Column)-[:FK_TO*1..3]->(:Column)<-[:HAS_COLUMN]-(t2:Table {name: 'transactions'})
RETURN path
```

#### 시나리오 2: AI 컨텍스트 생성

```cypher
-- Oracle(NL2SQL)이 사용할 스키마 컨텍스트 추출
MATCH (ds:DataSource {name: 'erp_db'})-[:HAS_SCHEMA]->(s:Schema)-[:HAS_TABLE]->(t:Table)-[:HAS_COLUMN]->(c:Column)
RETURN t.name, t.description, collect({
    name: c.name,
    type: c.dtype,
    nullable: c.nullable,
    description: c.description
}) as columns
```

#### 시나리오 3: 데이터 영향도 분석

```cypher
-- "processes 테이블을 변경하면 영향받는 테이블은?"
MATCH (t:Table {name: 'processes'})-[:HAS_COLUMN]->(:Column)<-[:FK_TO]-(:Column)<-[:HAS_COLUMN]-(affected:Table)
RETURN DISTINCT affected.name
```

---

## 4. 4계층 아키텍처 (K-AIR 유산)

Weaver는 K-AIR의 4계층 데이터 아키텍처를 계승한다.

```
┌──────────────────────────────────────────────────────────────┐
│  다이나믹 레이어 (Vision 모듈 담당)                           │
│  - OLAP 피벗 분석                                            │
│  - What-if 시뮬레이션                                        │
│  - 분석 결과 물리화 (Materialized View)                       │
├──────────────────────────────────────────────────────────────┤
│  도메인 레이어 (Oracle + Synapse 모듈 담당)                   │
│  - NL2SQL (자연어 → SQL)                                     │
│  - 온톨로지 기반 지식그래프                                   │
│  - 멀티축 벡터 검색                                           │
├──────────────────────────────────────────────────────────────┤
│  ★ 데이터 패브릭 레이어 (Weaver 모듈 담당) ★                 │
│  - MindsDB 통합 (다중 DB SQL 게이트웨이)                      │
│  - 메타데이터 추출 어댑터 (PostgreSQL/MySQL/Oracle)           │
│  - Neo4j 메타데이터 그래프                                    │
│  - ETL 파이프라인 (Airflow)                                   │
├──────────────────────────────────────────────────────────────┤
│  피지컬 레이어 (실제 데이터베이스들)                           │
│  - ERP DB (PostgreSQL)                                        │
│  - 재무 시스템 DB (MySQL/Oracle)                              │
│  - CRM DB (다양)                                              │
│  - 문서 저장소 (MongoDB/S3)                                   │
└──────────────────────────────────────────────────────────────┘

데이터 흐름:
  피지컬 → [ETL/Weaver] → 패브릭 → [Oracle/Synapse] → 도메인 → [Vision] → 다이나믹
```

---

## 5. Weaver와 다른 Axiom 모듈의 관계

| 모듈 | Weaver에 대한 의존 | 인터페이스 |
|------|-------------------|-----------|
| **Oracle (NL2SQL)** | 메타데이터 그래프(Neo4j)에서 스키마 컨텍스트 조회 | Neo4j 직접 접근 또는 Weaver API |
| **Vision (분석)** | 쿼리 실행을 Weaver를 통해 수행 | `POST /api/query` |
| **Synapse (온톨로지)** | 메타데이터 그래프를 온톨로지와 연동 | Neo4j 공유 또는 API |
| **Canvas (UI)** | 데이터소스 관리 UI, 쿼리 편집기 | Weaver REST API |
| **Core (공통)** | 인증/인가 미들웨어 제공 | JWT 검증 |

### 금지사항

- Oracle/Vision이 대상 DB에 **직접 연결하지 않는다** (반드시 Weaver 경유)
- Canvas가 MindsDB에 **직접 API 호출하지 않는다** (반드시 Weaver API 경유)
- Weaver가 비즈니스 로직(도메인 특화 절차, 집계 계산 등)을 **포함하지 않는다**

### 필수사항

- 모든 외부 DB 접근은 Weaver를 통한다
- 메타데이터 변경은 Neo4j 그래프에 반영한다
- 쿼리 실행 결과에 대한 캐싱은 Weaver 계층에서 처리한다

---

## 6. 관련 문서

| 문서 | 설명 |
|------|------|
| `01_architecture/adapter-pattern.md` | 어댑터 패턴 설계 상세 |
| `03_backend/mindsdb-client.md` | MindsDB 클라이언트 구현 |
| `06_data/neo4j-schema.md` | Neo4j 메타데이터 그래프 스키마 |
| `06_data/data-flow.md` | 데이터 흐름 상세 |
| `99_decisions/ADR-001-mindsdb-gateway.md` | MindsDB 선택 근거 |
| `99_decisions/ADR-003-neo4j-metadata.md` | Neo4j 메타데이터 저장소 선택 근거 |
| `01_architecture/metadata-service.md` | 메타데이터 서비스 아키텍처 |
