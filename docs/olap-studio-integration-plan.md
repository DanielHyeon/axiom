# OLAP Studio 통합 설계서 (B안 — 독립 마이크로서비스)

> **작성일:** 2026-03-21
> **버전:** v1.0
> **상태:** 초안 (Draft)
> **대상 독자:** 아키텍트, 백엔드/프론트엔드 개발자, DevOps

---

## 1. 목표와 설계 원칙

### 1.1 목표

KAIR `data-platform-olap`의 고유 기능을 Axiom 생태계에 편입하되, 기존 서비스 경계(Vision, Oracle, Synapse, Weaver, Core)를 훼손하지 않고 다음 기능을 **독립적으로** 제공한다.

| # | 기능 | 설명 |
|---|------|------|
| 1 | **스타 스키마 기반 OLAP 피벗** | Dimension/Fact/Measure 구조 위의 드래그 앤 드롭 피벗 분석 |
| 2 | **Mondrian XML 기반 큐브 관리** | XML 스키마 생성·검증·배포·버전 이력 |
| 3 | **ETL 파이프라인 정의/실행** | Source → Transform → Target 3단 파이프라인 설계 및 실행 상태 추적 |
| 4 | **Airflow DAG 생성/동기화** | ETL 정의를 Airflow DAG로 변환하여 배포·트리거·상태 조회 |
| 5 | **데이터 리니지 관리** | 원천 테이블 → 스테이징 → Fact/Dimension → Cube → Report 경로 추적 |
| 6 | **큐브 AI 생성** | LLM 기반 큐브 자동 생성 후 사용자 검토·승인 워크플로 |
| 7 | **DDL + 샘플 데이터 생성** | AI 보조 스키마 DDL 및 테스트용 샘플 데이터 생성 |
| 8 | **탐색형 NL2SQL** | 큐브 컨텍스트 기반의 자연어 → SQL 변환 (운영형 Oracle NL2SQL과 분리) |

### 1.2 설계 원칙

#### 원칙 1: 데이터 모델 소유권은 단일 서비스가 가진다

스타 스키마, 큐브, Mondrian XML, ETL 파이프라인, 리니지 원천 이벤트의 소유자는 **OLAP Studio 단일 서비스**다. 다른 서비스가 이 데이터를 "읽을" 수는 있지만 "쓰지" 않는다. 이 원칙은 KAIR의 `data-platform-olap` 내부에서 스타 스키마/큐브/ETL/Mondrian이 강결합된 메타모델을 형성하고 있어, 기능을 분산하면 변경 경로가 복잡해지는 문제를 방지한다.

#### 원칙 2: Axiom 표준은 공통 계약만 공유한다

인증(JWT), 멀티테넌트(`X-Tenant-Id`), 프로젝트 컨텍스트(`X-Project-Id`), 감사 로그, 이벤트 포맷(Redis Streams + Outbox), 에러 응답 포맷만 공통화한다. 도메인 로직이나 저장 스키마는 OLAP Studio가 독자적으로 관리한다.

#### 원칙 3: 사용자 경험은 통합하되 런타임은 분리한다

사용자는 Axiom Canvas(React SPA) 안의 메뉴로 접근하지만, 배포·스케일링·장애 격리는 독립 서비스(컨테이너) 단위로 처리한다. Canvas는 기존 서비스(Vision, Oracle)와 동일한 방식으로 OLAP Studio API를 호출한다.

#### 원칙 4: 기존 서비스와는 흡수 통합이 아니라 연계 통합을 한다

Vision/Oracle/Synapse/Weaver는 OLAP Studio의 기능을 직접 소유하지 않는다. 이벤트 소비, 메타데이터 조회 링크, 그래프 동기화 등 **연계** 수준의 통합만 수행한다. 이렇게 하면 OLAP Studio를 독립적으로 버전업하거나, 향후 별도 제품으로 분리하는 것이 가능해진다.

---

## 2. 서비스 경계

### 2.1 신규 서비스: OLAP Studio (port 9005)

**내부 포트:** 8005
**외부 매핑:** 9005 → 8005
**PostgreSQL 스키마:** `olap`
**Redis 키 접두사:** `olap:`

#### 책임 (Owns)

| 영역 | 상세 |
|------|------|
| 데이터 소스 등록 | OLAP 전용 데이터소스 관리 (Weaver의 데이터 패브릭 카탈로그와 별개) |
| 스타 스키마 모델 관리 | Dimension / Fact / Measure / Join 정의 및 버전관리 |
| Mondrian XML | XML import/export, 검증(XSD + 의미 규칙), 배포 |
| 큐브 생성/수정/버전관리 | 큐브 정의, 차원/측정값 바인딩, 게시/아카이브 라이프사이클 |
| OLAP 피벗 질의 실행 | 큐브 기반 SQL 생성 + 실행 + 결과 반환 |
| ETL 파이프라인 정의/실행 | Source/Target/Transform 사양 정의, 실행 상태(큐/러닝/성공/실패) 추적 |
| Airflow DAG 배포/실행 연계 | ETL 정의 → DAG 코드 변환, Airflow REST API 통한 배포·트리거·상태 조회 |
| 데이터 리니지 생성/갱신 | 엔티티·엣지 관리, 변경 시 Outbox 이벤트 발행 |
| DDL / 샘플 데이터 생성 | AI 보조 DDL 생성, 테스트 데이터 생성 |
| 큐브 AI 보조 생성 | LLM 기반 큐브 초안 생성, 사용자 검토 흐름 |
| 탐색형 NL2SQL | 큐브 메타데이터 컨텍스트 기반 자연어 → SQL 변환 및 실행 |

#### 비책임 (Does NOT Own)

| 영역 | 소유 서비스 | 비고 |
|------|-----------|------|
| KPI/Driver/What-if/RCA | Vision | 온톨로지 기반 분석은 Vision 전담 |
| 전사 의미 온톨로지 | Synapse | 5계층 온톨로지 Neo4j 그래프 |
| 운영형 NL2SQL 승인 워크플로우 | Oracle | ReAct + HIL + 가드레일 |
| 공통 사용자/권한 관리 | Core | JWT, RBAC, 멀티테넌트 |
| 조직 공통 그래프 저장소의 주도권 | Synapse | Neo4j 마스터 |

### 2.2 기존 서비스와의 역할 정리

#### Vision (9100 → 내부 8000)

| 현재 역할 | OLAP Studio 통합 후 변경 |
|----------|----------------------|
| 온톨로지 기반 분석 피벗 (`/api/analytics/*`) | 유지 — Vision의 피벗은 KPI/Measure/Driver 축 중심 |
| KPI → Driver → RCA → What-if | 유지 — 변경 없음 |
| `cube_manager.py` (102 LOC), `etl_manager.py` (156 LOC) | **단계적 폐기** — Phase 8에서 OLAP Studio로 위임 전환 |
| OLAP Studio 집계 결과 참조 | 신규 — 큐브 메타데이터/집계 결과를 API 조회로 참조 가능 |

Vision의 기존 `olap.py` (437 LOC) API는 온톨로지 피벗 전용으로 유지하되, 스타 스키마 기반 분석은 OLAP Studio가 담당한다.

#### Oracle (9004 → 내부 8004)

| 현재 역할 | OLAP Studio 통합 후 변경 |
|----------|----------------------|
| 운영형 NL2SQL (ReAct + HIL + 승인/가드레일) | 유지 — 변경 없음 |
| 쿼리 실행 + 피드백 분석 | 유지 |
| OLAP Studio 탐색형 NL2SQL | **분리 운영** — 같은 LLM을 사용하되 승인 워크플로 없음 |
| Query Policy/Audit 계약 | 추후 공유 가능 (Phase 8) |

Oracle의 NL2SQL은 "운영형" (승인 필수, 히스토리 감사, 피드백 루프)이고, OLAP Studio의 NL2SQL은 "탐색형" (큐브 컨텍스트 내 즉시 실행)으로 성격이 다르다.

#### Synapse (9003 → 내부 8003)

| 현재 역할 | OLAP Studio 통합 후 변경 |
|----------|----------------------|
| Neo4j 기반 5계층 온톨로지 | 유지 — 변경 없음 |
| 그래프 소비/조회/시각화 | 유지 |
| OLAP Studio 리니지 이벤트 소비 | **신규** — `olap.lineage.updated` 이벤트를 소비하여 Neo4j lineage 노드/관계 동기화 |
| 리니지 의미 규칙 원소유자 | **아님** — 리니지 엔티티/엣지의 SSOT는 OLAP Studio PostgreSQL |

#### Weaver (9001 → 내부 8001)

| 현재 역할 | OLAP Studio 통합 후 변경 |
|----------|----------------------|
| 데이터 패브릭/카탈로그 허브 | 유지 |
| 메타데이터 인트로스펙션 | 유지 |
| OLAP Studio 메타데이터 수집 | **신규** — 큐브 게시/ETL 완료 이벤트를 소비하여 카탈로그에 요약 메타데이터 반영 |
| ETL/큐브 엔진 소유 | **아님** — 엔진 자체는 OLAP Studio 소유 |

### 2.3 상위 수준 연동 구조

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Canvas (React SPA)                            │
│                                                                      │
│  /analysis/olap          → Vision API (온톨로지 기반 피벗)            │
│  /analysis/olap-studio   → OLAP Studio API (스타 스키마 피벗)         │
│  /analysis/nl2sql        → Oracle API (운영형 NL2SQL)                │
│  /analysis/insight       → Vision API (KPI 임팩트 분석)               │
│  /data/etl               → OLAP Studio API (ETL 관리)               │
│  /data/cubes             → OLAP Studio API (큐브 관리)               │
│  /data/lineage           → OLAP Studio API + Synapse API (연계)      │
│  /data/sources           → OLAP Studio API (OLAP 전용 데이터소스)     │
│  /data/datasources       → Weaver API (데이터 패브릭 카탈로그)        │
│  /data/ontology          → Synapse API (5계층 온톨로지)               │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP (JWT + Headers)
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Gateway (인증/라우팅)                              │
│                                                                      │
│  /api/gateway/vision/**   → Vision (9100)                            │
│  /api/gateway/oracle/**   → Oracle (9004)                            │
│  /api/gateway/synapse/**  → Synapse (9003)                           │
│  /api/gateway/weaver/**   → Weaver (9001)                            │
│  /api/gateway/core/**     → Core (9002)                              │
│  /api/gateway/olap/**     → OLAP Studio (9005)   ◄── 신규            │
│                                                                      │
│  공통: JWT 검증, X-Tenant-Id, X-Project-Id, X-User-Id 주입            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐  ┌────────────────────┐  ┌──────────────────────┐
│   Vision     │  │   OLAP Studio      │  │   Oracle / Synapse   │
│   (9100)     │  │   (9005) ◄── 신규   │  │   / Weaver / Core    │
│              │  │                    │  │                      │
│  - OLAP 피벗 │  │  - 큐브 관리        │  │  - NL2SQL (운영형)    │
│    (온톨로지)│  │  - Mondrian XML    │  │  - 온톨로지 (Neo4j)   │
│  - KPI/RCA   │  │  - ETL 파이프라인   │  │  - 데이터 패브릭      │
│  - What-if   │  │  - Airflow 연계    │  │  - 사용자/인증        │
│              │  │  - 피벗 (스타스키마)│  │                      │
│              │  │  - 리니지           │  │                      │
│              │  │  - AI 큐브 생성     │  │                      │
│              │  │  - 탐색형 NL2SQL   │  │                      │
└──────┬───────┘  └─────────┬──────────┘  └──────────┬───────────┘
       │                    │                        │
       └────────────────────┼────────────────────────┘
                            ▼
              ┌──────────────────────────┐
              │    Redis Streams         │
              │    (이벤트 버스)           │
              │                          │
              │  olap.etl.run.completed  │
              │  olap.cube.published     │
              │  olap.lineage.updated    │
              │  olap.airflow.dag.deployed│
              └──────────┬───────────────┘
                         │ 소비
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     Synapse         Weaver         Canvas
     (Neo4j 동기화)  (카탈로그 반영)  (UI 알림)
```

```
┌──────────────────────────────────────────────────────────────┐
│                 OLAP Studio 내부 구조                          │
│                                                              │
│  FastAPI (port 8005)                                         │
│  ├─ api/                                                     │
│  │  ├─ data_sources.py     ← 데이터소스 CRUD + 테스트        │
│  │  ├─ models.py           ← 스타 스키마 모델 관리            │
│  │  ├─ cubes.py            ← 큐브 CRUD + 게시                │
│  │  ├─ mondrian.py         ← XML 생성·검증·배포              │
│  │  ├─ pivot.py            ← 피벗 질의 실행 + 뷰 관리        │
│  │  ├─ etl.py              ← 파이프라인 CRUD + 실행          │
│  │  ├─ airflow.py          ← DAG 생성·배포·트리거            │
│  │  ├─ lineage.py          ← 리니지 조회 + 영향 분석         │
│  │  ├─ ai.py               ← AI 생성 + 승인/반려             │
│  │  ├─ nl2sql.py           ← 탐색형 NL2SQL                   │
│  │  └─ health.py           ← /health, /ready, /metrics      │
│  ├─ services/                                                │
│  │  ├─ cube_service.py                                       │
│  │  ├─ mondrian_service.py                                   │
│  │  ├─ etl_service.py                                        │
│  │  ├─ airflow_client.py                                     │
│  │  ├─ pivot_engine.py                                       │
│  │  ├─ lineage_service.py                                    │
│  │  ├─ ai_generation_service.py                              │
│  │  └─ nl2sql_service.py                                     │
│  ├─ db/                                                      │
│  │  ├─ models.py           ← SQLAlchemy ORM 모델             │
│  │  ├─ repositories/       ← Repository 패턴 구현            │
│  │  └─ migrations/         ← Alembic 마이그레이션            │
│  ├─ events/                                                  │
│  │  ├─ publisher.py        ← Outbox 기반 이벤트 발행         │
│  │  └─ relay_worker.py     ← Outbox → Redis Streams 릴레이  │
│  ├─ core/                                                    │
│  │  ├─ config.py           ← 환경 설정                       │
│  │  ├─ context.py          ← RequestContext 미들웨어          │
│  │  ├─ auth.py             ← 권한 체크 의존성               │
│  │  └─ errors.py           ← 표준 에러 포맷                  │
│  └─ main.py                                                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. DB 스키마 설계

### 기본 원칙

1. **JSON 파일 저장 제거** — KAIR의 파일 기반 저장을 PostgreSQL로 전환한다.
2. **tenant_id, project_id를 모든 주요 엔티티에 포함** — 멀티테넌트 RLS 강제.
3. **생성/수정/삭제/audit/version 필드 표준화** — Axiom 공통 필드 규격 준수.
4. **큰 정의 데이터는 JSONB 활용** — 가변 구조(계층, 속성, 변환 사양 등)는 JSONB로 유연하게 처리.
5. **실행 로그/이벤트 로그는 append-only** — 수정 불가, 삭제는 보존 정책에 의해서만.
6. **PostgreSQL 스키마 접두사: `olap`** — 기존 `core`, `synapse`, `vision`, `weaver`, `oracle` 스키마와 동일한 패턴.

### 공통 필드 규격

모든 주요 엔티티에 적용되는 공통 필드 규격:

```sql
id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
tenant_id     UUID NOT NULL,
project_id    UUID NOT NULL,
created_at    TIMESTAMP NOT NULL DEFAULT now(),
created_by    VARCHAR(100) NOT NULL,
updated_at    TIMESTAMP NOT NULL DEFAULT now(),
updated_by    VARCHAR(100) NOT NULL,
deleted_at    TIMESTAMP NULL,           -- 소프트 삭제
version_no    INT NOT NULL DEFAULT 1    -- 낙관적 동시성 제어
```

- `deleted_at`이 NULL이 아니면 소프트 삭제된 행으로 간주한다.
- `version_no`는 UPDATE 시 `WHERE version_no = :expected` 조건으로 낙관적 락을 구현한다.
- `tenant_id + project_id`는 모든 쿼리의 WHERE 절에 포함되어야 한다.

### 3.1 데이터 소스 — `olap.data_sources`

**목적:** OLAP Studio 전용 원천 DB/파일/웨어하우스 연결 정보 관리. Weaver의 데이터 패브릭 카탈로그와는 별도로, OLAP 분석 파이프라인에 특화된 연결 정보를 저장한다.

```sql
-- 원천 데이터 연결 정보 관리
CREATE TABLE olap.data_sources (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id              UUID NOT NULL,
    project_id             UUID NOT NULL,
    name                   VARCHAR(200) NOT NULL,
    source_type            VARCHAR(50) NOT NULL,   -- POSTGRES, MYSQL, ORACLE, CSV, PARQUET, DUCKDB
    connection_config      JSONB NOT NULL DEFAULT '{}',
    credential_ref         VARCHAR(200),            -- secret manager reference (비밀번호 직접 저장 금지)
    is_active              BOOLEAN NOT NULL DEFAULT true,
    last_health_status     VARCHAR(20),             -- OK, ERROR, TIMEOUT
    last_health_checked_at TIMESTAMP,
    created_at             TIMESTAMP NOT NULL DEFAULT now(),
    created_by             VARCHAR(100) NOT NULL,
    updated_at             TIMESTAMP NOT NULL DEFAULT now(),
    updated_by             VARCHAR(100) NOT NULL,
    deleted_at             TIMESTAMP,
    UNIQUE(tenant_id, project_id, name)
);

-- 인덱스: 테넌트/프로젝트 기반 조회 최적화
CREATE INDEX idx_data_sources_tenant_project
    ON olap.data_sources(tenant_id, project_id)
    WHERE deleted_at IS NULL;

-- connection_config JSONB 구조 예시:
-- {
--   "host": "db.example.com",
--   "port": 5432,
--   "database": "warehouse",
--   "schema": "public",
--   "ssl_mode": "require",
--   "pool_size": 5,
--   "timeout_seconds": 30
-- }
```

### 3.2 스타 스키마 모델 — `olap.models`, `olap.dimensions`, `olap.facts`, `olap.joins`

**목적:** Dimension/Fact 기반 스타 스키마를 정의하고 버전관리한다. 하나의 Model은 하나의 데이터 소스에 연결되며, 여러 Dimension과 Fact를 포함한다.

```sql
-- 스타 스키마 모델 (최상위 컨테이너)
CREATE TABLE olap.models (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    project_id        UUID NOT NULL,
    name              VARCHAR(200) NOT NULL,
    description       TEXT,
    source_id         UUID REFERENCES olap.data_sources(id),
    model_status      VARCHAR(20) NOT NULL DEFAULT 'DRAFT',   -- DRAFT, ACTIVE, ARCHIVED
    semantic_version  VARCHAR(20) NOT NULL DEFAULT '0.1.0',
    published_at      TIMESTAMP,
    created_at        TIMESTAMP NOT NULL DEFAULT now(),
    created_by        VARCHAR(100) NOT NULL,
    updated_at        TIMESTAMP NOT NULL DEFAULT now(),
    updated_by        VARCHAR(100) NOT NULL,
    deleted_at        TIMESTAMP,
    version_no        INT NOT NULL DEFAULT 1,
    UNIQUE(tenant_id, project_id, name)
);

CREATE INDEX idx_models_tenant_project
    ON olap.models(tenant_id, project_id)
    WHERE deleted_at IS NULL;

-- 차원 테이블 정의
CREATE TABLE olap.dimensions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id            UUID NOT NULL REFERENCES olap.models(id) ON DELETE CASCADE,
    name                VARCHAR(200) NOT NULL,
    physical_table_name VARCHAR(200) NOT NULL,
    grain_description   TEXT,                      -- 이 차원의 입도(grain) 설명
    column_map          JSONB NOT NULL DEFAULT '{}',
    -- column_map 예시: {"dim_key": "customer_id", "display_name": "customer_name", "sort_key": "customer_name"}
    hierarchies         JSONB NOT NULL DEFAULT '[]',
    -- hierarchies 예시: [{"name": "지역", "levels": ["country", "region", "city"]}]
    attributes          JSONB NOT NULL DEFAULT '[]',
    -- attributes 예시: [{"name": "age_group", "column": "age_group", "type": "string"}]
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(model_id, name)
);

CREATE INDEX idx_dimensions_model ON olap.dimensions(model_id);

-- 팩트 테이블 정의
CREATE TABLE olap.facts (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id                  UUID NOT NULL REFERENCES olap.models(id) ON DELETE CASCADE,
    name                      VARCHAR(200) NOT NULL,
    physical_table_name       VARCHAR(200) NOT NULL,
    grain_description         TEXT,                -- 이 팩트의 입도(grain) 설명
    measures                  JSONB NOT NULL DEFAULT '[]',
    -- measures 예시: [{"name": "revenue", "column": "revenue_amt", "type": "SUM", "format": "#,##0.00"}]
    degenerate_dimensions     JSONB NOT NULL DEFAULT '[]',
    -- degenerate_dimensions 예시: [{"name": "order_number", "column": "order_no"}]
    created_at                TIMESTAMP NOT NULL DEFAULT now(),
    updated_at                TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(model_id, name)
);

CREATE INDEX idx_facts_model ON olap.facts(model_id);

-- 조인 정의 (Fact ↔ Dimension, Dimension ↔ Dimension)
CREATE TABLE olap.joins (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id            UUID NOT NULL REFERENCES olap.models(id) ON DELETE CASCADE,
    left_entity_type    VARCHAR(20) NOT NULL,    -- FACT, DIMENSION
    left_entity_id      UUID NOT NULL,
    right_entity_type   VARCHAR(20) NOT NULL,    -- FACT, DIMENSION
    right_entity_id     UUID NOT NULL,
    join_type           VARCHAR(20) NOT NULL DEFAULT 'INNER',  -- INNER, LEFT, RIGHT, FULL
    join_expression     TEXT NOT NULL,            -- 예: "fact.customer_id = dim_customer.id"
    cardinality         VARCHAR(10) NOT NULL DEFAULT '1:N',    -- 1:1, 1:N, N:1, N:N
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_joins_model ON olap.joins(model_id);
```

### 3.3 큐브 / Mondrian — `olap.cubes`, `olap.cube_dimensions`, `olap.cube_measures`, `olap.mondrian_documents`

**목적:** 스타 스키마 모델 위에 논리적 큐브를 정의하고, Mondrian XML 스키마를 관리한다. 큐브는 DRAFT → VALIDATED → PUBLISHED 라이프사이클을 따른다.

```sql
-- 큐브 정의 (모델 위의 논리적 뷰)
CREATE TABLE olap.cubes (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    project_id        UUID NOT NULL,
    model_id          UUID REFERENCES olap.models(id),
    name              VARCHAR(200) NOT NULL,
    description       TEXT,
    cube_status       VARCHAR(20) NOT NULL DEFAULT 'DRAFT',   -- DRAFT, VALIDATED, PUBLISHED, FAILED
    ai_generated      BOOLEAN NOT NULL DEFAULT false,         -- AI가 생성한 큐브 여부
    default_currency  VARCHAR(10),                            -- 기본 통화 코드 (KRW, USD 등)
    default_locale    VARCHAR(10),                            -- 기본 로케일 (ko, en 등)
    metadata          JSONB NOT NULL DEFAULT '{}',
    -- metadata 예시: {"tags": ["manufacturing", "quality"], "owner_team": "data-eng"}
    created_at        TIMESTAMP NOT NULL DEFAULT now(),
    created_by        VARCHAR(100) NOT NULL,
    updated_at        TIMESTAMP NOT NULL DEFAULT now(),
    updated_by        VARCHAR(100) NOT NULL,
    deleted_at        TIMESTAMP,
    version_no        INT NOT NULL DEFAULT 1,
    UNIQUE(tenant_id, project_id, name)
);

CREATE INDEX idx_cubes_tenant_project
    ON olap.cubes(tenant_id, project_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_cubes_model ON olap.cubes(model_id);

-- 큐브에 포함된 차원 바인딩
CREATE TABLE olap.cube_dimensions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cube_id               UUID NOT NULL REFERENCES olap.cubes(id) ON DELETE CASCADE,
    dimension_name        VARCHAR(200) NOT NULL,
    source_dimension_id   UUID REFERENCES olap.dimensions(id),   -- 모델의 차원 참조
    display_order         INT NOT NULL DEFAULT 0,
    visibility_rule       JSONB NOT NULL DEFAULT '{}',
    -- visibility_rule 예시: {"roles": ["ADMIN", "ANALYST"], "hidden_levels": ["internal_code"]}
    UNIQUE(cube_id, dimension_name)
);

CREATE INDEX idx_cube_dimensions_cube ON olap.cube_dimensions(cube_id);

-- 큐브에 포함된 측정값 정의
CREATE TABLE olap.cube_measures (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cube_id           UUID NOT NULL REFERENCES olap.cubes(id) ON DELETE CASCADE,
    measure_name      VARCHAR(200) NOT NULL,
    aggregation_type  VARCHAR(30) NOT NULL DEFAULT 'SUM',   -- SUM, COUNT, AVG, MIN, MAX, DISTINCT_COUNT
    expression        TEXT,                                  -- 계산 측정값일 경우 SQL 표현식
    format_string     VARCHAR(50),                           -- 표시 포맷 (예: "#,##0.00", "0.0%")
    display_order     INT NOT NULL DEFAULT 0,
    UNIQUE(cube_id, measure_name)
);

CREATE INDEX idx_cube_measures_cube ON olap.cube_measures(cube_id);

-- Mondrian XML 문서 (큐브당 버전 이력)
CREATE TABLE olap.mondrian_documents (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cube_id               UUID NOT NULL REFERENCES olap.cubes(id) ON DELETE CASCADE,
    xml_content           TEXT NOT NULL,                       -- Mondrian XML 전문
    xml_hash              VARCHAR(64) NOT NULL,                -- SHA-256 해시 (중복 방지)
    document_status       VARCHAR(20) NOT NULL DEFAULT 'GENERATED',  -- GENERATED, VALIDATED, DEPLOYED, ERROR
    validation_result     JSONB,
    -- validation_result 예시: {"valid": true, "warnings": [], "errors": []}
    deployed_at           TIMESTAMP,
    created_at            TIMESTAMP NOT NULL DEFAULT now(),
    updated_at            TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_mondrian_cube ON olap.mondrian_documents(cube_id);
```

### 3.4 ETL — `olap.etl_pipelines`, `olap.etl_runs`, `olap.etl_run_steps`

**목적:** ETL 파이프라인 정의, 실행 이력, 단계별 실행 상태를 관리한다. Airflow DAG와의 연계 정보도 포함한다.

```sql
-- ETL 파이프라인 정의
CREATE TABLE olap.etl_pipelines (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    project_id        UUID NOT NULL,
    name              VARCHAR(200) NOT NULL,
    description       TEXT,
    pipeline_type     VARCHAR(20) NOT NULL DEFAULT 'BATCH',   -- BATCH, INCREMENTAL, FULL_LOAD
    source_config     JSONB NOT NULL DEFAULT '{}',
    -- source_config 예시: {"source_id": "uuid", "tables": ["orders", "customers"], "filter": "created_at > '2026-01-01'"}
    target_config     JSONB NOT NULL DEFAULT '{}',
    -- target_config 예시: {"target_schema": "warehouse", "target_table": "fact_orders", "write_mode": "append"}
    transform_spec    JSONB NOT NULL DEFAULT '{}',
    -- transform_spec 예시: {"steps": [{"type": "rename", "from": "col_a", "to": "column_a"}, {"type": "filter", "condition": "status != 'DELETED'"}]}
    schedule_cron     VARCHAR(100),                           -- cron 표현식 (예: "0 2 * * *")
    airflow_dag_id    VARCHAR(200),                           -- Airflow DAG 식별자
    status            VARCHAR(20) NOT NULL DEFAULT 'DRAFT',   -- DRAFT, READY, DEPLOYED, PAUSED, ERROR
    created_at        TIMESTAMP NOT NULL DEFAULT now(),
    created_by        VARCHAR(100) NOT NULL,
    updated_at        TIMESTAMP NOT NULL DEFAULT now(),
    updated_by        VARCHAR(100) NOT NULL,
    deleted_at        TIMESTAMP,
    version_no        INT NOT NULL DEFAULT 1,
    UNIQUE(tenant_id, project_id, name)
);

CREATE INDEX idx_etl_pipelines_tenant_project
    ON olap.etl_pipelines(tenant_id, project_id)
    WHERE deleted_at IS NULL;

-- ETL 실행 이력 (append-only)
CREATE TABLE olap.etl_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES olap.etl_pipelines(id),
    run_status      VARCHAR(20) NOT NULL DEFAULT 'QUEUED',    -- QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED
    trigger_type    VARCHAR(20) NOT NULL DEFAULT 'MANUAL',    -- MANUAL, SCHEDULED, EVENT
    started_at      TIMESTAMP,
    ended_at        TIMESTAMP,
    rows_read       BIGINT DEFAULT 0,
    rows_written    BIGINT DEFAULT 0,
    error_message   TEXT,
    metrics         JSONB NOT NULL DEFAULT '{}',
    -- metrics 예시: {"bytes_transferred": 1048576, "peak_memory_mb": 256, "parallel_tasks": 4}
    triggered_by    VARCHAR(100) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_etl_runs_pipeline ON olap.etl_runs(pipeline_id);
CREATE INDEX idx_etl_runs_status ON olap.etl_runs(run_status, created_at);

-- ETL 실행 단계별 상태 (append-only)
CREATE TABLE olap.etl_run_steps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES olap.etl_runs(id) ON DELETE CASCADE,
    step_name       VARCHAR(200) NOT NULL,
    step_order      INT NOT NULL,
    step_status     VARCHAR(20) NOT NULL DEFAULT 'PENDING',   -- PENDING, RUNNING, SUCCEEDED, FAILED, SKIPPED
    started_at      TIMESTAMP,
    ended_at        TIMESTAMP,
    metrics         JSONB NOT NULL DEFAULT '{}',
    error_message   TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_etl_run_steps_run ON olap.etl_run_steps(run_id);
```

### 3.5 피벗 / 질의 이력 — `olap.pivot_views`, `olap.query_history`

**목적:** 사용자가 저장한 피벗 뷰 레이아웃과 질의 실행 이력을 관리한다.

```sql
-- 저장된 피벗 뷰 (사용자별 레이아웃)
CREATE TABLE olap.pivot_views (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    cube_id         UUID REFERENCES olap.cubes(id),
    name            VARCHAR(200) NOT NULL,
    layout          JSONB NOT NULL DEFAULT '{}',
    -- layout 예시: {"rows": ["product_category"], "columns": ["year", "quarter"], "values": ["revenue", "quantity"], "aggregations": {"revenue": "SUM", "quantity": "COUNT"}}
    filter_config   JSONB NOT NULL DEFAULT '{}',
    -- filter_config 예시: {"year": {"op": "IN", "values": [2025, 2026]}, "region": {"op": "=", "value": "APAC"}}
    sort_config     JSONB NOT NULL DEFAULT '{}',
    -- sort_config 예시: {"column": "revenue", "direction": "DESC"}
    owner_user_id   VARCHAR(100) NOT NULL,
    is_shared       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMP
);

CREATE INDEX idx_pivot_views_tenant_project
    ON olap.pivot_views(tenant_id, project_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_pivot_views_owner
    ON olap.pivot_views(owner_user_id);

-- 질의 실행 이력 (append-only, 감사 + 성능 분석용)
CREATE TABLE olap.query_history (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    project_id       UUID NOT NULL,
    query_type       VARCHAR(20) NOT NULL,    -- PIVOT, SQL, NL2SQL
    cube_id          UUID,
    input_text       TEXT,                    -- NL2SQL인 경우 원문 자연어 질의
    generated_sql    TEXT,                    -- 실행된 SQL
    execution_ms     INT,                     -- 실행 시간 (밀리초)
    result_row_count INT,                     -- 결과 행 수
    status           VARCHAR(20) NOT NULL,    -- SUCCESS, ERROR, TIMEOUT
    error_message    TEXT,
    executed_by      VARCHAR(100) NOT NULL,
    created_at       TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_query_history_tenant_project
    ON olap.query_history(tenant_id, project_id, created_at DESC);

CREATE INDEX idx_query_history_cube
    ON olap.query_history(cube_id, created_at DESC);
```

### 3.6 리니지 — `olap.lineage_entities`, `olap.lineage_edges`

**목적:** 데이터 리니지를 엔티티-엣지 그래프로 관리한다. 이 테이블이 리니지의 SSOT(Single Source of Truth)이며, Synapse Neo4j로의 동기화는 이벤트 기반으로 이루어진다.

```sql
-- 리니지 엔티티 (노드)
CREATE TABLE olap.lineage_entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    entity_type     VARCHAR(30) NOT NULL,   -- SOURCE_TABLE, STAGING_TABLE, FACT, DIMENSION, CUBE, MEASURE, DAG, REPORT
    entity_key      VARCHAR(500) NOT NULL,  -- 고유 식별 키 (예: "warehouse.fact_orders", "cube:sales_cube")
    display_name    VARCHAR(200) NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    -- metadata 예시: {"schema": "warehouse", "row_count": 1500000, "last_refreshed": "2026-03-21T00:00:00Z"}
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, project_id, entity_type, entity_key)
);

CREATE INDEX idx_lineage_entities_tenant_project
    ON olap.lineage_entities(tenant_id, project_id);

CREATE INDEX idx_lineage_entities_type
    ON olap.lineage_entities(entity_type);

-- 리니지 엣지 (관계)
CREATE TABLE olap.lineage_edges (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id    UUID NOT NULL REFERENCES olap.lineage_entities(id) ON DELETE CASCADE,
    to_entity_id      UUID NOT NULL REFERENCES olap.lineage_entities(id) ON DELETE CASCADE,
    edge_type         VARCHAR(30) NOT NULL,   -- DERIVES_TO, LOADS_TO, DEPENDS_ON, GENERATES, FEEDS
    relation          JSONB NOT NULL DEFAULT '{}',
    -- relation 예시: {"transform_type": "aggregation", "columns_mapped": ["revenue", "quantity"], "pipeline_id": "uuid"}
    created_at        TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(from_entity_id, to_entity_id, edge_type)
);

CREATE INDEX idx_lineage_edges_from ON olap.lineage_edges(from_entity_id);
CREATE INDEX idx_lineage_edges_to ON olap.lineage_edges(to_entity_id);
```

### 3.7 AI 생성 결과 — `olap.ai_generations`

**목적:** AI가 생성한 큐브/DDL/샘플 데이터/매핑 결과를 저장하고, 사용자의 승인/반려 상태를 추적한다.

```sql
-- AI 생성 결과 및 승인 이력
CREATE TABLE olap.ai_generations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    project_id        UUID NOT NULL,
    generation_type   VARCHAR(30) NOT NULL,   -- CUBE, DDL, SAMPLE_DATA, SQL_EXPLAIN, MAPPING
    input_context     JSONB NOT NULL DEFAULT '{}',
    -- input_context 예시 (CUBE): {"source_tables": ["orders", "customers"], "business_goal": "매출 분석 큐브"}
    -- input_context 예시 (DDL): {"table_name": "dim_product", "columns_hint": ["id", "name", "category"]}
    result            JSONB NOT NULL DEFAULT '{}',
    -- result 예시 (CUBE): {"cube_name": "sales_cube", "dimensions": [...], "measures": [...], "confidence": 0.87}
    -- result 예시 (DDL): {"ddl": "CREATE TABLE ...", "sample_insert_count": 100}
    status            VARCHAR(20) NOT NULL DEFAULT 'COMPLETED',   -- COMPLETED, APPROVED, REJECTED
    approved_by       VARCHAR(100),
    approved_at       TIMESTAMP,
    rejection_reason  TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT now(),
    created_by        VARCHAR(100) NOT NULL
);

CREATE INDEX idx_ai_generations_tenant_project
    ON olap.ai_generations(tenant_id, project_id, created_at DESC);

CREATE INDEX idx_ai_generations_type
    ON olap.ai_generations(generation_type, status);
```

### 3.8 Outbox 이벤트 — `olap.outbox_events`

**목적:** Transactional Outbox 패턴으로 이벤트를 안전하게 발행한다. 비즈니스 트랜잭션과 이벤트 저장을 하나의 DB 트랜잭션으로 묶어 "쓰기 후 발행 실패" 문제를 방지한다.

```sql
-- Transactional Outbox (이벤트 안전 발행)
CREATE TABLE olap.outbox_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    aggregate_type  VARCHAR(50) NOT NULL,     -- CUBE, ETL_PIPELINE, ETL_RUN, LINEAGE, AI_GENERATION, AIRFLOW_DAG
    aggregate_id    UUID NOT NULL,
    event_type      VARCHAR(100) NOT NULL,    -- olap.etl.run.completed, olap.cube.published 등
    event_version   VARCHAR(10) NOT NULL DEFAULT '1.0',
    payload         JSONB NOT NULL,
    occurred_at     TIMESTAMP NOT NULL DEFAULT now(),
    published_at    TIMESTAMP,                -- 실제 Redis Streams 발행 시각
    publish_status  VARCHAR(20) NOT NULL DEFAULT 'PENDING'  -- PENDING, PUBLISHED, FAILED
);

-- Relay Worker가 PENDING 이벤트를 순서대로 처리하기 위한 인덱스
CREATE INDEX idx_outbox_pending
    ON olap.outbox_events(publish_status, occurred_at)
    WHERE publish_status = 'PENDING';

-- 특정 집합체의 이벤트 이력 조회용 인덱스
CREATE INDEX idx_outbox_aggregate
    ON olap.outbox_events(aggregate_type, aggregate_id, occurred_at);
```

### 3.9 스키마 초기화 스크립트

`scripts/init-db-schemas.sql`에 다음 라인을 추가해야 한다:

```sql
CREATE SCHEMA IF NOT EXISTS olap;
```

---

## 4. 이벤트 계약

### 4.1 공통 이벤트 Envelope

모든 OLAP Studio 이벤트는 Axiom 표준 Envelope 형식을 따른다. Redis Streams의 `olap-events` 스트림으로 발행되며, 소비자 그룹 방식으로 처리한다.

```json
{
  "eventId": "550e8400-e29b-41d4-a716-446655440000",
  "eventType": "olap.etl.run.completed",
  "eventVersion": "1.0",
  "occurredAt": "2026-03-21T12:00:00Z",
  "tenantId": "a1b2c3d4-0000-0000-0000-000000000001",
  "projectId": "p1p2p3p4-0000-0000-0000-000000000001",
  "producer": "olap-studio",
  "traceId": "trace-abc-123-def-456",
  "payload": { }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `eventId` | UUID | 이벤트 고유 식별자 (멱등성 보장 키) |
| `eventType` | string | 이벤트 유형 (점 표기법: `서비스.도메인.동작`) |
| `eventVersion` | string | 이벤트 스키마 버전 (하위 호환성 관리) |
| `occurredAt` | ISO-8601 | 이벤트 발생 시각 |
| `tenantId` | UUID | 테넌트 식별자 |
| `projectId` | UUID | 프로젝트 식별자 |
| `producer` | string | 이벤트 생산자 서비스명 |
| `traceId` | string | 분산 추적 ID (OpenTelemetry 연계) |
| `payload` | object | 이벤트별 상세 데이터 |

### 4.2 주요 이벤트 목록

#### 이벤트 1: `olap.etl.run.completed` — ETL 실행 완료

ETL 파이프라인 실행이 성공적으로 완료되었을 때 발행한다.

```json
{
  "eventId": "evt-001-etl-run-completed",
  "eventType": "olap.etl.run.completed",
  "eventVersion": "1.0",
  "occurredAt": "2026-03-21T14:30:00Z",
  "tenantId": "a1b2c3d4-0000-0000-0000-000000000001",
  "projectId": "p1p2p3p4-0000-0000-0000-000000000001",
  "producer": "olap-studio",
  "traceId": "trace-etl-run-001",
  "payload": {
    "pipelineId": "pl-550e8400-uuid",
    "pipelineName": "일일 주문 적재",
    "runId": "run-660e9500-uuid",
    "status": "SUCCEEDED",
    "triggerType": "SCHEDULED",
    "rowsRead": 150000,
    "rowsWritten": 148750,
    "durationMs": 45200,
    "startedAt": "2026-03-21T14:29:15Z",
    "endedAt": "2026-03-21T14:30:00Z",
    "stepsCompleted": 5,
    "totalSteps": 5
  }
}
```

**소비자:**

| 소비자 | 처리 내용 |
|--------|----------|
| Canvas (알림) | 사용자에게 ETL 완료 토스트/알림 표시 |
| Weaver (메타데이터) | 카탈로그에 테이블 최종 갱신 시각, 행 수 등 메타데이터 반영 |
| Synapse (리니지) | ETL 실행 결과를 반영하여 리니지 그래프 갱신 트리거 |
| 모니터링/감사 | 실행 이력 대시보드 및 감사 로그 기록 |

---

#### 이벤트 2: `olap.etl.run.failed` — ETL 실행 실패

ETL 파이프라인 실행이 실패했을 때 발행한다.

```json
{
  "eventId": "evt-002-etl-run-failed",
  "eventType": "olap.etl.run.failed",
  "eventVersion": "1.0",
  "occurredAt": "2026-03-21T15:10:00Z",
  "tenantId": "a1b2c3d4-0000-0000-0000-000000000001",
  "projectId": "p1p2p3p4-0000-0000-0000-000000000001",
  "producer": "olap-studio",
  "traceId": "trace-etl-run-002",
  "payload": {
    "pipelineId": "pl-550e8400-uuid",
    "pipelineName": "일일 주문 적재",
    "runId": "run-770f0600-uuid",
    "status": "FAILED",
    "triggerType": "MANUAL",
    "failedStep": {
      "stepName": "transform_orders",
      "stepOrder": 3,
      "startedAt": "2026-03-21T15:09:30Z",
      "endedAt": "2026-03-21T15:10:00Z"
    },
    "errorCode": "TRANSFORM_TYPE_MISMATCH",
    "errorMessage": "Column 'order_date' expected type TIMESTAMP but got VARCHAR in source table 'raw_orders'",
    "rowsReadBeforeFailure": 75000,
    "durationMs": 55000
  }
}
```

**소비자:**

| 소비자 | 처리 내용 |
|--------|----------|
| Canvas (알림) | 사용자에게 ETL 실패 경고 알림, 실패 단계 하이라이트 |
| 모니터링/감사 | 에러 로그 기록, 운영팀 알림 트리거 |
| Watch (Core) | WatchRule 조건에 매칭 시 WatchAlert 생성 |

---

#### 이벤트 3: `olap.cube.published` — 큐브 게시 완료

큐브가 PUBLISHED 상태로 전환되었을 때 발행한다.

```json
{
  "eventId": "evt-003-cube-published",
  "eventType": "olap.cube.published",
  "eventVersion": "1.0",
  "occurredAt": "2026-03-21T16:00:00Z",
  "tenantId": "a1b2c3d4-0000-0000-0000-000000000001",
  "projectId": "p1p2p3p4-0000-0000-0000-000000000001",
  "producer": "olap-studio",
  "traceId": "trace-cube-pub-001",
  "payload": {
    "cubeId": "cube-880e1700-uuid",
    "cubeName": "매출 분석 큐브",
    "modelId": "model-990f2800-uuid",
    "modelName": "영업 스타 스키마",
    "mondrianDocumentId": "mond-aa0e3900-uuid",
    "versionNo": 3,
    "dimensionCount": 5,
    "measureCount": 8,
    "publishedBy": "data_engineer_01"
  }
}
```

**소비자:**

| 소비자 | 처리 내용 |
|--------|----------|
| Canvas (캐시) | 큐브 목록 캐시 무효화, 피벗 UI에 신규 큐브 반영 |
| Vision (참조) | 큐브 메타데이터를 참조하여 KPI 분석 컨텍스트 갱신 |
| Weaver (카탈로그) | 카탈로그에 큐브 메타데이터 인덱싱 (이름, 차원, 측정값) |
| 모니터링/감사 | 큐브 게시 이력 기록 |

---

#### 이벤트 4: `olap.mondrian.validation.failed` — Mondrian 문서 검증 실패

Mondrian XML 문서의 검증이 실패했을 때 발행한다.

```json
{
  "eventId": "evt-004-mondrian-validation-failed",
  "eventType": "olap.mondrian.validation.failed",
  "eventVersion": "1.0",
  "occurredAt": "2026-03-21T16:15:00Z",
  "tenantId": "a1b2c3d4-0000-0000-0000-000000000001",
  "projectId": "p1p2p3p4-0000-0000-0000-000000000001",
  "producer": "olap-studio",
  "traceId": "trace-mondrian-val-001",
  "payload": {
    "cubeId": "cube-880e1700-uuid",
    "cubeName": "매출 분석 큐브",
    "documentId": "mond-bb1f4a00-uuid",
    "errors": [
      {
        "code": "INVALID_HIERARCHY",
        "severity": "ERROR",
        "message": "Hierarchy 'product_category'의 레벨 'sub_category'에 해당하는 컬럼이 물리 테이블에 존재하지 않습니다.",
        "location": "Dimension[@name='Product']/Hierarchy[@name='product_category']/Level[@name='sub_category']"
      },
      {
        "code": "MISSING_FOREIGN_KEY",
        "severity": "ERROR",
        "message": "Fact 테이블 'fact_orders'에서 Dimension 'dim_product'로의 외래키 'product_id' 조인이 정의되지 않았습니다.",
        "location": "Cube[@name='sales_cube']/DimensionUsage[@name='Product']"
      }
    ],
    "totalErrors": 2,
    "totalWarnings": 0
  }
}
```

**소비자:**

| 소비자 | 처리 내용 |
|--------|----------|
| Canvas (알림) | 큐브 관리 화면에 검증 실패 표시, 에러 상세 패널 |
| 모니터링/감사 | 검증 실패 로그 기록 |

---

#### 이벤트 5: `olap.lineage.updated` — 리니지 갱신 완료

리니지 엔티티/엣지가 추가·수정·삭제되었을 때 발행한다.

```json
{
  "eventId": "evt-005-lineage-updated",
  "eventType": "olap.lineage.updated",
  "eventVersion": "1.0",
  "occurredAt": "2026-03-21T17:00:00Z",
  "tenantId": "a1b2c3d4-0000-0000-0000-000000000001",
  "projectId": "p1p2p3p4-0000-0000-0000-000000000001",
  "producer": "olap-studio",
  "traceId": "trace-lineage-upd-001",
  "payload": {
    "entityCount": 12,
    "edgeCount": 18,
    "rootEntityType": "CUBE",
    "rootEntityId": "cube-880e1700-uuid",
    "rootEntityName": "매출 분석 큐브",
    "changeType": "INCREMENTAL",
    "addedEntities": 2,
    "removedEntities": 0,
    "addedEdges": 3,
    "removedEdges": 1,
    "affectedEntityTypes": ["FACT", "DIMENSION", "CUBE"]
  }
}
```

**소비자:**

| 소비자 | 처리 내용 |
|--------|----------|
| Synapse (Neo4j) | PostgreSQL lineage 엔티티/엣지를 Neo4j 노드/관계로 동기화 |
| Canvas (리니지 UI) | 리니지 그래프 캐시 갱신, 변경된 노드 하이라이트 |
| Weaver (카탈로그) | 리니지 요약 메타데이터 갱신 (upstream/downstream 수) |

---

#### 이벤트 6: `olap.airflow.dag.deployed` — Airflow DAG 배포 완료

ETL 파이프라인이 Airflow DAG로 성공적으로 배포되었을 때 발행한다.

```json
{
  "eventId": "evt-006-airflow-dag-deployed",
  "eventType": "olap.airflow.dag.deployed",
  "eventVersion": "1.0",
  "occurredAt": "2026-03-21T18:00:00Z",
  "tenantId": "a1b2c3d4-0000-0000-0000-000000000001",
  "projectId": "p1p2p3p4-0000-0000-0000-000000000001",
  "producer": "olap-studio",
  "traceId": "trace-airflow-dep-001",
  "payload": {
    "pipelineId": "pl-550e8400-uuid",
    "pipelineName": "일일 주문 적재",
    "dagId": "olap_daily_order_load_a1b2c3d4",
    "deploymentStatus": "SUCCESS",
    "scheduleCron": "0 2 * * *",
    "dagVersion": "v2",
    "airflowBaseUrl": "https://airflow.internal.axiom.kr",
    "previousDagId": "olap_daily_order_load_a1b2c3d4_v1"
  }
}
```

**소비자:**

| 소비자 | 처리 내용 |
|--------|----------|
| Canvas (ETL UI) | ETL 파이프라인 카드에 Airflow 동기화 상태 "배포 완료" 표시 |
| 모니터링/감사 | DAG 배포 이력 기록 |

---

#### 이벤트 7: `olap.ai.cube.generated` — AI 큐브 생성 완료

AI가 큐브를 자동 생성했을 때 발행한다. 사용자 검토가 필요함을 알린다.

```json
{
  "eventId": "evt-007-ai-cube-generated",
  "eventType": "olap.ai.cube.generated",
  "eventVersion": "1.0",
  "occurredAt": "2026-03-21T19:00:00Z",
  "tenantId": "a1b2c3d4-0000-0000-0000-000000000001",
  "projectId": "p1p2p3p4-0000-0000-0000-000000000001",
  "producer": "olap-studio",
  "traceId": "trace-ai-cube-gen-001",
  "payload": {
    "generationId": "gen-cc2e5b00-uuid",
    "cubeId": "cube-dd3f6c00-uuid",
    "cubeName": "AI 생성: 고객 이탈 분석 큐브",
    "confidence": 0.82,
    "requiresReview": true,
    "dimensionCount": 4,
    "measureCount": 6,
    "inputContext": {
      "sourceTables": ["customers", "orders", "returns", "support_tickets"],
      "businessGoal": "고객 이탈률 분석"
    },
    "generatedBy": "gpt-4o",
    "generationDurationMs": 12500
  }
}
```

**소비자:**

| 소비자 | 처리 내용 |
|--------|----------|
| Canvas (알림) | "AI가 큐브를 생성했습니다. 검토가 필요합니다." 알림 표시 |
| 모니터링/감사 | AI 생성 이력 기록, 승인/반려 워크플로 시작 |

---

## 5. Gateway 라우트 설계

### 5.1 라우트 매핑

Gateway에서 OLAP Studio로의 라우트 매핑. Gateway는 `/api/gateway/olap` 접두사를 제거하고 OLAP Studio의 내부 경로로 프록시한다.

```
/api/gateway/olap/**  →  olap-studio:8005/**
```

| # | Gateway 경로 | OLAP Studio 내부 경로 | 설명 |
|---|-------------|---------------------|------|
| 1 | `/api/gateway/olap/data-sources/**` | `/data-sources/**` | 데이터소스 CRUD + 테스트 + 스키마 |
| 2 | `/api/gateway/olap/models/**` | `/models/**` | 스타 스키마 모델/차원/팩트/조인 |
| 3 | `/api/gateway/olap/cubes/**` | `/cubes/**` | 큐브 CRUD + 검증 + 게시 |
| 4 | `/api/gateway/olap/mondrian/**` | `/mondrian/**` | Mondrian XML 생성/검증/배포 |
| 5 | `/api/gateway/olap/pivot/**` | `/pivot/**` | 피벗 질의 실행 + 뷰 관리 |
| 6 | `/api/gateway/olap/etl/**` | `/etl/**` | ETL 파이프라인 + 실행 이력 |
| 7 | `/api/gateway/olap/airflow/**` | `/airflow/**` | Airflow DAG 관리 |
| 8 | `/api/gateway/olap/lineage/**` | `/lineage/**` | 리니지 조회 + 영향 분석 |
| 9 | `/api/gateway/olap/ai/**` | `/ai/**` | AI 생성 + 승인/반려 |
| 10 | `/api/gateway/olap/nl2sql/**` | `/nl2sql/**` | 탐색형 NL2SQL |
| 11 | `/api/gateway/olap/health/**` | `/health/**` | 헬스체크/레디니스/메트릭 |

### 5.2 Gateway 주입 헤더

Gateway는 JWT 검증 후 다음 8개 헤더를 OLAP Studio로 전달한다. OLAP Studio는 이 헤더를 신뢰하고 별도 JWT 검증을 하지 않는다(Gateway 뒤에서만 접근 가능).

| # | 헤더 | 타입 | 설명 | 예시 |
|---|------|------|------|------|
| 1 | `Authorization` | string | 원본 JWT Bearer 토큰 (디버깅/감사용) | `Bearer eyJhbG...` |
| 2 | `X-User-Id` | UUID | JWT에서 추출한 사용자 ID | `user-123-456` |
| 3 | `X-User-Name` | string | 사용자 표시명 | `홍길동` |
| 4 | `X-Tenant-Id` | UUID | 테넌트 ID | `tenant-a1b2c3d4` |
| 5 | `X-Project-Id` | UUID | 현재 선택된 프로젝트 ID | `project-p1p2p3p4` |
| 6 | `X-Request-Id` | UUID | 요청별 고유 ID (중복 감지, 멱등성) | `req-550e8400` |
| 7 | `X-Trace-Id` | string | 분산 추적 ID (OpenTelemetry) | `trace-abc-123` |
| 8 | `X-Roles` | string | 쉼표 구분 역할 목록 | `admin,data_engineer` |

### 5.3 Gateway 수준 정책

#### 인증 검증

- Gateway에서 JWT 유효성(만료, 서명, 발급자)을 **우선 검증**한다.
- 만료/무효 토큰은 Gateway에서 `401 Unauthorized`를 반환하며, OLAP Studio까지 도달하지 않는다.
- Refresh Token 갱신은 Core 서비스가 담당한다.

#### 프로젝트 컨텍스트 강제

- `X-Project-Id` 헤더가 없거나 빈 값인 경우, project scope API (`/data-sources`, `/models`, `/cubes`, `/etl`, `/pivot`, `/lineage`, `/ai`, `/nl2sql`)에 대해 `400 Bad Request`를 반환한다.
- `/health/**`는 프로젝트 컨텍스트 없이도 접근 가능하다.

#### Rate Limiting

| API 그룹 | 제한 | 근거 |
|----------|------|------|
| `/pivot/execute` | 60회/분/사용자 | 대량 피벗 질의 방지 |
| `/etl/pipelines/{id}/run` | 10회/분/사용자 | ETL 실행 폭주 방지 |
| `/ai/**` | 20회/분/사용자 | LLM 호출 비용 관리 |
| `/nl2sql/execute` | 30회/분/사용자 | SQL 실행 부하 관리 |
| 그 외 | 120회/분/사용자 | 일반 CRUD 보호 |

#### SSE/Streaming 정책

- ETL 실행 상태 실시간 업데이트를 위해 SSE(Server-Sent Events)를 사용할 경우:
  - Gateway proxy timeout: 300초 (5분)
  - Response buffering: 비활성화 (`X-Accel-Buffering: no`)
  - Keep-alive: 30초 간격 ping

#### 에러 포맷 래핑

OLAP Studio의 에러 응답은 Axiom 표준 포맷으로 래핑한다:

```json
{
  "error": {
    "code": "OLAP_CUBE_NOT_FOUND",
    "message": "큐브를 찾을 수 없습니다.",
    "details": {
      "cubeId": "cube-880e1700-uuid"
    },
    "requestId": "req-550e8400",
    "traceId": "trace-abc-123",
    "timestamp": "2026-03-21T12:00:00Z"
  }
}
```

---

## 6. React 메뉴/화면 구조

### 6.1 메뉴 구조

OLAP Studio 관련 메뉴는 기존 Canvas 사이드바의 "분석"과 "데이터" 섹션에 통합한다.

| 상위 메뉴 | 하위 메뉴 | 라우트 경로 | 백엔드 서비스 | 비고 |
|----------|----------|------------|-------------|------|
| 분석 | 온톨로지 피벗 | `/analysis/olap` | Vision (9100) | 기존 유지 |
| 분석 | **OLAP Studio** | `/analysis/olap-studio` | **OLAP Studio (9005)** | 신규 |
| 분석 | NL2SQL | `/analysis/nl2sql` | Oracle (9004) | 기존 유지 |
| 분석 | KPI 인사이트 | `/analysis/insight` | Vision (9100) | 기존 유지 |
| 분석 | What-if | `/analysis/whatif/wizard` | Vision (9100) | 기존 유지 |
| 데이터 | **ETL 파이프라인** | `/data/etl` | **OLAP Studio (9005)** | 신규 |
| 데이터 | **큐브 관리** | `/data/cubes` | **OLAP Studio (9005)** | 신규 |
| 데이터 | **데이터 리니지** | `/data/lineage` | **OLAP Studio (9005)** | 기존 리니지 화면 대체 |
| 데이터 | **데이터 소스** | `/data/sources` | **OLAP Studio (9005)** | 신규 (OLAP 전용) |
| 데이터 | 온톨로지 | `/data/ontology` | Synapse (9003) | 기존 유지 |
| 데이터 | 데이터 패브릭 | `/data/datasources` | Weaver (9001) | 기존 유지 |

#### routes.ts 변경 사항

```typescript
// 기존 ROUTES 객체에 추가
export const ROUTES = {
  // ... 기존 라우트 ...
  ANALYSIS: {
    OLAP: '/analysis/olap',
    OLAP_STUDIO: '/analysis/olap-studio',    // 신규
    NL2SQL: '/analysis/nl2sql',
    INSIGHT: '/analysis/insight',
    WHATIF_WIZARD: '/analysis/whatif/wizard',
  },
  DATA: {
    ONTOLOGY: '/data/ontology',
    DATASOURCES: '/data/datasources',
    SOURCES: '/data/sources',                 // 신규 (OLAP 전용)
    ETL: '/data/etl',                         // 신규
    CUBES: '/data/cubes',                     // 신규
    LINEAGE: '/data/lineage',                 // 기존 경로 유지, 백엔드 변경
    // ... 기존 라우트 ...
  },
  // ...
} as const;
```

### 6.2 화면별 상세 구성

#### A. `/analysis/olap-studio` — 피벗 분석

**레이아웃:** 3컬럼 + 상단 바 + 하단 탭

```
┌─────────────────────────────────────────────────────────────────┐
│ 프로젝트: [드롭다운]  큐브: [드롭다운]  [실행] [저장] [공유]      │
├──────────┬──────────────────────────────────┬───────────────────┤
│          │                                  │                   │
│ 큐브/뷰  │     Pivot Builder (중앙)          │  필터/차원/측정값  │
│ 목록     │                                  │  패널             │
│          │  ┌─ 행 영역 ─┐  ┌─ 값 영역 ─┐   │                   │
│ 📁 매출  │  │ product  │  │ revenue  │   │  🔍 필터           │
│ 📁 재고  │  │ region   │  │ quantity │   │  📊 차원           │
│ 📁 인사  │  └──────────┘  └──────────┘   │  📏 측정값          │
│          │  ┌─ 열 영역 ─┐  ┌─ 필터 ──┐   │  ↕ 정렬             │
│ 저장된   │  │ year     │  │ status  │   │  🎨 서식           │
│ 뷰 목록  │  │ quarter  │  │         │   │                   │
│          │  └──────────┘  └─────────┘   │                   │
│          │                                  │                   │
│          │  ┌─ 결과 그리드 ───────────────┐  │                   │
│          │  │       Q1    Q2    Q3    Q4  │  │                   │
│          │  │ 전자  100   120   110   130 │  │                   │
│          │  │ 식품   80    90    85    95 │  │                   │
│          │  │ 의류   50    55    52    60 │  │                   │
│          │  └────────────────────────────┘  │                   │
├──────────┴──────────────────────────────────┴───────────────────┤
│ [SQL 보기]  [실행 로그]  [데이터 미리보기]                         │
│                                                                 │
│ SELECT product_category, year, quarter, SUM(revenue) ...        │
└─────────────────────────────────────────────────────────────────┘
```

**기능 상세:**

- **좌측 패널 (240px):** 큐브 목록(트리 구조)과 사용자가 저장한 Pivot View 목록. 클릭하면 해당 큐브/뷰를 로딩한다.
- **상단 바:** 프로젝트 컨텍스트 선택, 큐브 선택 드롭다운, 실행(피벗 질의 전송), 저장(현재 레이아웃 저장), 공유(다른 사용자와 Pivot View 공유) 버튼.
- **중앙 — Pivot Builder:** 드래그 앤 드롭으로 차원을 행/열/필터 영역에 배치하고, 측정값을 값 영역에 배치한다. `@dnd-kit/core` 라이브러리를 사용한다.
- **중앙 — 결과 그리드:** 피벗 질의 결과를 TanStack Table로 렌더링. 셀 포맷팅(통화, 퍼센트), 소계/합계 행, 열 정렬 지원.
- **우측 패널 (280px):** 선택된 차원/측정값의 상세 설정. 필터 조건(IN, =, BETWEEN, LIKE), 정렬(ASC/DESC), 서식(숫자 포맷, 조건부 서식).
- **하단 탭:**
  - SQL 보기: Monaco Editor (읽기 전용)로 생성된 SQL 표시
  - 실행 로그: 최근 실행 이력 테이블 (시각, 행 수, 소요 시간, 상태)
  - 데이터 미리보기: 원본 테이블 데이터 100행 미리보기

**피처 슬라이스 구조:**

```
features/olap-studio/
├── api/
│   ├── olapStudioApi.ts        — TanStack Query 기반 API 호출
│   └── index.ts
├── components/
│   ├── OlapStudioPage.tsx       — 페이지 레이아웃 컨테이너
│   ├── CubeSelector.tsx         — 큐브/뷰 목록 패널
│   ├── PivotCanvas.tsx          — 드래그앤드롭 Pivot Builder
│   ├── MeasurePanel.tsx         — 측정값 설정 패널
│   ├── DimensionPanel.tsx       — 차원/필터/정렬/서식 패널
│   ├── PivotResultGrid.tsx      — 결과 그리드 (TanStack Table)
│   ├── PivotSqlPreview.tsx      — SQL 미리보기 (Monaco Editor)
│   ├── PivotExecutionLog.tsx    — 실행 이력 테이블
│   └── index.ts
├── hooks/
│   ├── usePivotBuilder.ts       — 드래그앤드롭 상태 관리
│   ├── usePivotExecution.ts     — 피벗 질의 실행/결과
│   ├── usePivotViews.ts         — 저장된 뷰 CRUD
│   └── index.ts
├── store/
│   └── useOlapStudioStore.ts    — Zustand 스토어
├── types/
│   ├── pivot.ts                 — 피벗 관련 타입
│   ├── cube.ts                  — 큐브 관련 타입
│   └── index.ts
└── utils/
    ├── pivotFormatter.ts        — 셀 포맷팅 유틸
    └── index.ts
```

---

#### B. `/data/etl` — ETL 파이프라인 관리

**레이아웃:** 상단 상태 요약 + 목록/상세 분할

```
┌─────────────────────────────────────────────────────────────────┐
│ ETL 파이프라인 관리                   [카드뷰] [테이블뷰] [+ 새로 만들기] │
├───────┬──────────┬──────────┬──────────────────────────────────┤
│ 실행중 │ 실패     │ 대기     │ 최근 성공                         │
│   3   │   1      │   5      │ 12 (오늘)                         │
├───────┴──────────┴──────────┴──────────────────────────────────┤
│                                                                 │
│  ┌─ 파이프라인 카드 ─────────────────────────────────────────┐  │
│  │ 📦 일일 주문 적재                          DEPLOYED ✅    │  │
│  │ BATCH | 매일 02:00 | Airflow: synced                      │  │
│  │ 마지막 실행: 2026-03-21 02:00 (성공, 148K행, 45초)        │  │
│  │ [실행] [편집] [이력] [Airflow]                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ 파이프라인 카드 ─────────────────────────────────────────┐  │
│  │ 📦 시간별 재고 동기화                      PAUSED ⏸      │  │
│  │ INCREMENTAL | 매시간 | Airflow: pending                   │  │
│  │ 마지막 실행: 2026-03-20 15:00 (실패 — 타입 불일치)         │  │
│  │ [실행] [편집] [이력] [Airflow]                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ... (더 보기)                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**파이프라인 상세 편집 화면 (모달 또는 슬라이드오버):**

```
┌─────────────────────────────────────────────────────────────────┐
│ 파이프라인 편집: 일일 주문 적재                     [저장] [취소]│
├─────────────────────────────────────────────────────────────────┤
│ [기본 정보] [소스 설정] [변환 설정] [타겟 설정] [스케줄]         │
├─────────────────────────────────────────────────────────────────┤
│ 소스 설정:                                                       │
│   데이터소스: [영업 DB ▼]                                        │
│   테이블: [orders ✓] [order_items ✓] [customers □]              │
│   필터: created_at > '2026-01-01'                                │
│                                                                 │
│ 변환 설정:                                                       │
│   1. 컬럼 이름 변경: col_a → column_a                            │
│   2. 필터: status != 'DELETED'                                   │
│   3. 타입 변환: order_date VARCHAR → TIMESTAMP                   │
│   [+ 변환 단계 추가]                                             │
│                                                                 │
│ 타겟 설정:                                                       │
│   스키마: warehouse                                              │
│   테이블: fact_orders                                            │
│   쓰기 모드: [APPEND ▼]                                         │
└─────────────────────────────────────────────────────────────────┘
```

**기능 상세:**

- **상태 카드:** 실행중/실패/대기/최근 성공 파이프라인 수를 실시간 표시. 클릭 시 해당 상태 필터링.
- **카드/테이블 뷰 전환:** 카드뷰(시각적)와 테이블뷰(밀도 높은 목록) 전환.
- **파이프라인 상세 편집:** 4개 탭으로 소스/변환/타겟/스케줄 설정. 변환 단계는 드래그 앤 드롭으로 순서 변경 가능.
- **실행 이력 테이블:** 파이프라인별 실행 이력. 상태, 시작/종료 시각, 처리 행 수, 소요 시간, 에러 메시지 표시.
- **Airflow 동기화 패널:** DAG 배포 상태(synced/pending/error), 최근 Airflow 실행 결과, Airflow UI 딥링크.

**피처 슬라이스 구조:**

```
features/etl/
├── api/
│   └── etlApi.ts
├── components/
│   ├── EtlPipelineListPage.tsx      — 파이프라인 목록 페이지
│   ├── EtlPipelineCard.tsx          — 파이프라인 카드 컴포넌트
│   ├── EtlPipelineEditor.tsx        — 파이프라인 편집 폼
│   ├── EtlRunHistoryTable.tsx       — 실행 이력 테이블
│   ├── EtlStatusSummary.tsx         — 상태 요약 카드
│   ├── AirflowSyncPanel.tsx         — Airflow 동기화 패널
│   ├── TransformStepEditor.tsx      — 변환 단계 편집기
│   └── index.ts
├── hooks/
│   ├── useEtlPipelines.ts
│   ├── useEtlRuns.ts
│   └── useAirflowSync.ts
├── store/
│   └── useEtlStore.ts
└── types/
    └── etl.ts
```

---

#### C. `/data/cubes` — 큐브 관리

**레이아웃:** 상단 탭 네비게이션 + 컨텐츠 영역

```
┌─────────────────────────────────────────────────────────────────┐
│ 큐브 관리                                                        │
│ [모델] [차원] [팩트] [조인] [큐브] [Mondrian XML] [AI 생성]       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ── 모델 탭 ──────────────────────────────────────────────────── │
│                                                                 │
│  스타 스키마 다이어그램 (시각적):                                  │
│                                                                 │
│       ┌──────────┐                                              │
│       │dim_time  │                                              │
│       │ year     │──┐                                           │
│       │ quarter  │  │                                           │
│       └──────────┘  │   ┌───────────────┐                      │
│                     ├──▶│ fact_orders    │                      │
│  ┌──────────────┐   │   │ revenue       │   ┌──────────┐       │
│  │dim_product   │──┘   │ quantity      │──▶│dim_region│       │
│  │ category     │       │ order_date    │   │ country  │       │
│  │ subcategory  │       └───────────────┘   │ region   │       │
│  └──────────────┘                           │ city     │       │
│                                              └──────────┘       │
│                                                                 │
│  모델 목록:                                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 이름          │ 상태   │ 소스       │ 차원 │ 팩트 │ 버전   │ │
│  │ 영업 스타스키마│ ACTIVE │ 영업 DB    │ 4    │ 2    │ 1.2.0  │ │
│  │ HR 분석       │ DRAFT  │ HR DB      │ 3    │ 1    │ 0.1.0  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ── Mondrian XML 탭 ──────────────────────────────────────────── │
│                                                                 │
│  Monaco Editor (XML 편집):                                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ <?xml version="1.0"?>                                      │ │
│  │ <Schema name="SalesCube">                                  │ │
│  │   <Cube name="Sales">                                      │ │
│  │     <Table name="fact_orders"/>                             │ │
│  │     <Dimension name="Product" ...>                         │ │
│  │       <Hierarchy hasAll="true" ...>                        │ │
│  │ ...                                                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│  [생성] [검증] [배포] [이력 보기]                                 │
│                                                                 │
│ ── AI 생성 탭 ───────────────────────────────────────────────── │
│                                                                 │
│  소스 테이블 선택: [orders ✓] [customers ✓] [products ✓]        │
│  비즈니스 목표: [매출 분석 큐브를 만들어 주세요                ]    │
│  [AI로 큐브 생성]                                                │
│                                                                 │
│  생성 결과:                                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 큐브명: AI 생성: 매출 분석 큐브 (confidence: 87%)           │ │
│  │ 차원: 4개, 측정값: 6개                                      │ │
│  │ [승인하여 큐브 생성] [수정 후 저장] [반려]                    │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**기능 상세:**

- **모델 탭:** 스타 스키마 모델 목록과 시각적 다이어그램. 다이어그램은 Fact 중심으로 Dimension을 별 모양으로 배치한다.
- **차원 탭:** 선택된 모델의 차원 목록. 차원별 물리 테이블, 컬럼 매핑, 계층(hierarchy), 속성 편집.
- **팩트 탭:** 선택된 모델의 팩트 목록. 측정값(measures), 퇴화 차원(degenerate dimensions) 편집.
- **조인 탭:** Fact ↔ Dimension, Dimension ↔ Dimension 간 조인 정의. 조인 타입, 표현식, 카디널리티 설정.
- **큐브 탭:** 큐브 목록 + 상세 편집. 큐브에 포함할 차원/측정값 선택, 가시성 규칙, 기본 통화/로케일 설정.
- **Mondrian XML 탭:** Monaco Editor로 XML 직접 편집. 생성(큐브 정의 → XML 변환), 검증(XSD + 의미 규칙), 배포, 이력 조회.
- **AI 생성 탭:** 소스 테이블 선택 + 비즈니스 목표 입력 → AI가 큐브 초안 생성 → 사용자 검토(승인/수정/반려).

**피처 슬라이스 구조:**

```
features/cube-management/
├── api/
│   └── cubeApi.ts
├── components/
│   ├── CubeManagementPage.tsx       — 탭 컨테이너 페이지
│   ├── StarSchemaDiagram.tsx        — 스타 스키마 시각화 (SVG/Canvas)
│   ├── ModelEditor.tsx              — 모델 CRUD 폼
│   ├── DimensionEditor.tsx          — 차원 편집 폼
│   ├── FactEditor.tsx               — 팩트 편집 폼
│   ├── JoinEditor.tsx               — 조인 편집 폼
│   ├── CubeEditor.tsx               — 큐브 편집 폼
│   ├── MondrianXmlEditor.tsx        — Mondrian XML 편집기 (Monaco)
│   ├── MondrianHistoryPanel.tsx     — XML 버전 이력
│   ├── AiCubeGenerationPanel.tsx    — AI 큐브 생성 패널
│   └── index.ts
├── hooks/
│   ├── useModels.ts
│   ├── useCubes.ts
│   ├── useMondrian.ts
│   └── useAiCubeGeneration.ts
├── store/
│   └── useCubeManagementStore.ts
└── types/
    ├── model.ts
    ├── cube.ts
    └── mondrian.ts
```

---

#### D. `/data/lineage` — 데이터 리니지

**레이아웃:** 3컬럼 (엔티티 탐색 + 그래프 + 상세)

```
┌─────────────────────────────────────────────────────────────────┐
│ 데이터 리니지                               [새로고침] [전체 보기]│
├──────────┬──────────────────────────────────┬───────────────────┤
│          │                                  │                   │
│ 엔티티   │     리니지 그래프 (중앙)           │  영향 분석 패널   │
│ 탐색     │                                  │                   │
│          │  SOURCE_TABLE    FACT             │  Upstream:        │
│ 📁 소스  │  ┌─────────┐   ┌──────────┐     │  - raw_orders     │
│  └ orders│  │raw_orders│──▶│fact_orders│    │  - raw_customers  │
│  └ custs │  └─────────┘   └────┬─────┘     │                   │
│ 📁 스테이│                      │            │  Downstream:      │
│  └ stg_  │  STAGING      ┌─────▼─────┐     │  - sales_cube     │
│ 📁 팩트  │  ┌──────┐    │ CUBE       │     │  - monthly_report │
│  └ fact_ │  │stg_  │───▶│ sales_cube │     │                   │
│ 📁 큐브  │  └──────┘    └─────┬─────┘     │  관련 ETL:        │
│  └ sales │                     │            │  - 일일 주문 적재  │
│ 📁 리포트│              ┌──────▼──────┐     │    (성공, 03-21)  │
│  └ monthly│             │ REPORT      │     │                   │
│          │              │monthly_report│    │  관련 큐브:       │
│          │              └─────────────┘     │  - 매출 분석 큐브  │
│          │                                  │    (PUBLISHED)    │
├──────────┴──────────────────────────────────┴───────────────────┤
│ 최근 이벤트 피드                                                  │
│ 🟢 03-21 14:30 ETL "일일 주문 적재" 완료 (148K행)                 │
│ 🔵 03-21 16:00 큐브 "매출 분석 큐브" v3 게시                      │
│ 🟡 03-20 15:00 ETL "시간별 재고 동기화" 실패 (타입 불일치)         │
└─────────────────────────────────────────────────────────────────┘
```

**기능 상세:**

- **좌측 — 엔티티 탐색 트리 (220px):** 엔티티를 유형별(소스/스테이징/팩트/차원/큐브/측정값/DAG/리포트)로 그룹화한 트리 뷰. 클릭하면 해당 엔티티를 중심으로 그래프를 포커싱.
- **중앙 — 리니지 그래프:** Cytoscape.js 또는 Mermaid.js 기반 DAG 그래프. 노드는 엔티티 유형별 아이콘/색상으로 구분. 엣지에 관계 유형(DERIVES_TO, LOADS_TO 등) 레이블 표시. 확대/축소/패닝/노드 선택 지원.
- **우측 — 영향 분석 패널 (260px):** 선택된 엔티티의 upstream(이 엔티티에 데이터를 제공하는 원천)과 downstream(이 엔티티의 데이터를 소비하는 대상) 목록. 관련 ETL 파이프라인과 큐브 정보 교차 표시.
- **하단 — 이벤트 피드:** 최근 ETL 완료/실패, 큐브 게시, 리니지 갱신 이벤트를 시간순으로 표시. `olap.etl.run.completed`, `olap.cube.published`, `olap.lineage.updated` 이벤트를 실시간 수신.

**피처 슬라이스 구조:**

```
features/lineage/
├── api/
│   └── lineageApi.ts
├── components/
│   ├── LineagePage.tsx              — 페이지 레이아웃 컨테이너
│   ├── LineageEntityTree.tsx        — 엔티티 탐색 트리
│   ├── LineageGraphCanvas.tsx       — 리니지 그래프 (Cytoscape)
│   ├── EntityImpactPanel.tsx        — upstream/downstream 영향 분석
│   ├── LineageEventFeed.tsx         — 최근 이벤트 피드
│   └── index.ts
├── hooks/
│   ├── useLineageGraph.ts
│   ├── useEntityImpact.ts
│   └── useLineageEvents.ts
├── store/
│   └── useLineageStore.ts
└── types/
    └── lineage.ts
```

---

#### E. `/data/sources` — 데이터 소스 관리

**레이아웃:** 카드 목록 + 상세 폼 + 스키마 브라우저

```
┌─────────────────────────────────────────────────────────────────┐
│ OLAP 데이터 소스                                   [+ 새로 만들기]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ 데이터소스 카드 ─────────────────┐  ┌─ 데이터소스 카드 ────┐ │
│  │ 🐘 영업 DB                        │  │ 🐬 HR DB            │ │
│  │ PostgreSQL | warehouse.example.com │  │ MySQL | hr.local    │ │
│  │ 상태: ✅ OK (2분 전 체크)          │  │ 상태: ✅ OK          │ │
│  │ 모델 2개 사용 중                   │  │ 모델 1개 사용 중     │ │
│  │ [편집] [테스트] [스키마 보기]       │  │ [편집] [테스트]      │ │
│  └───────────────────────────────────┘  └────────────────────┘ │
│                                                                 │
│  ┌─ 데이터소스 카드 ─────────────────┐  ┌─ 데이터소스 카드 ────┐ │
│  │ 🦆 분석용 DuckDB                  │  │ 📄 CSV 업로드        │ │
│  │ DuckDB | /data/analytics.duckdb   │  │ CSV | uploaded_files │ │
│  │ 상태: ✅ OK                        │  │ 상태: ⚠️ 미확인      │ │
│  │ 모델 0개 사용 중                   │  │ 모델 0개 사용 중     │ │
│  │ [편집] [테스트] [스키마 보기]       │  │ [편집] [테스트]      │ │
│  └───────────────────────────────────┘  └────────────────────┘ │
│                                                                 │
│ ── 연결 생성/편집 폼 (슬라이드오버) ──────────────────────────── │
│                                                                 │
│  이름: [영업 DB                    ]                             │
│  유형: [PostgreSQL ▼]                                           │
│  호스트: [warehouse.example.com    ]                             │
│  포트: [5432     ]  데이터베이스: [sales_db    ]                  │
│  스키마: [public    ]                                            │
│  인증: [Secret Manager 참조 ▼]  참조키: [secret/olap/sales-db ]  │
│  SSL: [require ▼]                                               │
│  풀 크기: [5  ]  타임아웃: [30초 ]                                │
│                                                                 │
│  [연결 테스트]  →  ✅ 연결 성공 (응답 12ms, 테이블 47개)          │
│                                                                 │
│  [저장] [취소]                                                   │
│                                                                 │
│ ── 스키마 브라우저 (모달) ────────────────────────────────────── │
│                                                                 │
│  📁 public                                                      │
│  ├── 📋 orders (152,340행)                                      │
│  │   ├── id (INT, PK)                                           │
│  │   ├── customer_id (INT, FK → customers.id)                   │
│  │   ├── order_date (TIMESTAMP)                                 │
│  │   ├── total_amount (DECIMAL)                                 │
│  │   └── status (VARCHAR)                                       │
│  ├── 📋 customers (8,450행)                                     │
│  │   └── ...                                                    │
│  └── 📋 products (1,230행)                                      │
│      └── ...                                                    │
└─────────────────────────────────────────────────────────────────┘
```

**기능 상세:**

- **카드 목록:** 등록된 데이터소스를 카드 형태로 표시. 소스 유형 아이콘, 호스트 정보, 연결 상태(OK/ERROR/TIMEOUT/미확인), 연결된 모델 수.
- **연결 생성/편집 폼:** 슬라이드오버 형태. 소스 유형에 따라 폼 필드가 동적으로 변경(PostgreSQL: 호스트/포트/DB/스키마, CSV: 파일 경로, DuckDB: 파일 경로). 비밀번호는 Secret Manager 참조만 저장(직접 저장 금지).
- **연결 테스트 패널:** [연결 테스트] 버튼 클릭 시 OLAP Studio 백엔드가 실제 연결을 시도하고 결과(성공/실패, 응답 시간, 테이블 수)를 반환.
- **스키마 브라우저:** 연결 성공 후 스키마/테이블/컬럼 구조를 트리 형태로 탐색. 각 테이블의 행 수, 컬럼의 타입/PK/FK 정보 표시.

**피처 슬라이스 구조:**

```
features/data-source/
├── api/
│   └── dataSourceApi.ts
├── components/
│   ├── DataSourceListPage.tsx       — 카드 목록 페이지
│   ├── DataSourceCard.tsx           — 데이터소스 카드 컴포넌트
│   ├── DataSourceForm.tsx           — 연결 생성/편집 폼
│   ├── ConnectionTestPanel.tsx      — 연결 테스트 결과 패널
│   ├── SchemaBrowser.tsx            — 스키마 트리 브라우저
│   └── index.ts
├── hooks/
│   ├── useDataSources.ts
│   ├── useConnectionTest.ts
│   └── useSchemaIntrospection.ts
├── store/
│   └── useDataSourceStore.ts
└── types/
    └── dataSource.ts
```

### 6.3 UX 주의사항

#### Vision 피벗과 OLAP Studio 피벗 구분

- **메뉴 이름:** "온톨로지 피벗"(Vision) vs "OLAP Studio"(OLAP Studio)로 명확히 구분한다.
- **아이콘:** 온톨로지 피벗은 그래프 아이콘, OLAP Studio는 큐브 아이콘을 사용한다.
- **설명 텍스트:** 각 메뉴에 한 줄 설명을 추가한다.
  - 온톨로지 피벗: "KPI/Measure/Driver 축 기반의 온톨로지 분석"
  - OLAP Studio: "스타 스키마 큐브 기반의 다차원 분석"

#### 교차 링크

- ETL 파이프라인에서 관련 큐브로 이동하는 링크
- 큐브에서 해당 큐브를 사용하는 피벗 뷰 목록으로 이동하는 링크
- 리니지 그래프에서 노드 클릭 시 해당 ETL/큐브/데이터소스 상세 페이지로 이동
- 피벗 결과에서 "리니지 보기" 버튼으로 데이터 출처 추적

#### AI 생성 배치

- AI 큐브 생성은 큐브 관리 화면의 **마지막 탭**으로 배치한다 (주 기능이 아닌 보조 액션).
- AI 생성 결과는 항상 사용자 검토를 거쳐야 하며, 자동 게시되지 않는다.
- AI 생성 탭에 "이 기능은 AI가 큐브 초안을 생성합니다. 반드시 검토 후 사용하세요." 안내 문구를 표시한다.

---

## 7. 인증/멀티테넌트 적용

### 7.1 인증 방식

OLAP Studio의 인증은 **Gateway 위임 방식**을 사용한다. 외부 요청은 모두 Gateway를 경유하며, Gateway에서 JWT를 검증한 후 내부 헤더로 사용자 컨텍스트를 전달한다. OLAP Studio는 별도 JWT 검증 없이 헤더를 신뢰한다.

```
사용자 요청 (JWT Bearer Token)
    │
    ▼
Gateway — JWT 검증 → 실패 시 401 반환
    │ 성공
    ▼
OLAP Studio — 헤더 기반 컨텍스트 읽기
    │
    ▼
서비스 로직 실행
```

**FastAPI RequestContext 모델:**

```python
from pydantic import BaseModel


class RequestContext(BaseModel):
    """
    Gateway에서 전달받은 요청 컨텍스트.
    모든 서비스 레이어에서 tenant/project scope 강제에 사용한다.
    """
    user_id: str
    user_name: str
    tenant_id: str
    project_id: str
    roles: list[str]
    trace_id: str | None = None
    request_id: str | None = None
```

**FastAPI 의존성 함수:**

```python
from fastapi import Request, HTTPException


async def get_request_context(request: Request) -> RequestContext:
    """
    요청 헤더에서 RequestContext를 추출한다.
    필수 헤더가 누락되면 400 Bad Request를 반환한다.
    """
    tenant_id = request.headers.get("X-Tenant-Id")
    project_id = request.headers.get("X-Project-Id")
    user_id = request.headers.get("X-User-Id")
    user_name = request.headers.get("X-User-Name", "unknown")
    roles_header = request.headers.get("X-Roles", "")
    trace_id = request.headers.get("X-Trace-Id")
    request_id = request.headers.get("X-Request-Id")

    if not all([tenant_id, project_id, user_id]):
        raise HTTPException(
            status_code=400,
            detail="필수 컨텍스트 헤더가 누락되었습니다 (X-Tenant-Id, X-Project-Id, X-User-Id)"
        )

    return RequestContext(
        user_id=user_id,
        user_name=user_name,
        tenant_id=tenant_id,
        project_id=project_id,
        roles=[r.strip() for r in roles_header.split(",") if r.strip()],
        trace_id=trace_id,
        request_id=request_id,
    )
```

### 7.2 멀티테넌트 강제

모든 데이터 접근 쿼리에 tenant_id와 project_id 조건을 강제한다.

**Repository 계층 규칙:**

```python
async def get_cubes(self, ctx: RequestContext) -> list[Cube]:
    """
    큐브 목록 조회 — 반드시 tenant_id + project_id scope 적용.
    """
    query = (
        select(CubeModel)
        .where(CubeModel.tenant_id == ctx.tenant_id)
        .where(CubeModel.project_id == ctx.project_id)
        .where(CubeModel.deleted_at.is_(None))
        .order_by(CubeModel.updated_at.desc())
    )
    result = await self.session.execute(query)
    return result.scalars().all()
```

**관리자 예외 처리:**

- `admin` 역할의 사용자가 테넌트 전체 데이터를 조회해야 하는 경우(예: 시스템 모니터링), 서비스 레이어에서 **명시적으로** scope을 확장한다.
- Repository 기본 메서드에는 항상 scope이 적용되며, 관리자 전용 메서드를 별도로 정의한다: `get_cubes_admin(self, tenant_id: str | None = None)`

### 7.3 권한 모델

#### 역할 → Capability 매핑

| Axiom 역할 | OLAP Studio Capability | 설명 |
|-----------|----------------------|------|
| **ADMIN** | 모든 capability | 전체 관리 권한 |
| **PMO** | `datasource:read`, `etl:read`, `cube:read`, `cube:publish`, `pivot:read`, `pivot:save`, `lineage:read`, `ai:read`, `nl2sql:read` | 조회 + 실행 승인 + 큐브 게시 |
| **DATA_ENGINEER** | `datasource:read`, `datasource:write`, `etl:read`, `etl:edit`, `etl:run`, `cube:read`, `cube:write`, `cube:publish`, `mondrian:edit`, `mondrian:deploy`, `pivot:read`, `pivot:save`, `lineage:read`, `ai:generate`, `nl2sql:execute` | ETL/소스/큐브 편집, 실행, 배포 |
| **ANALYST** | `datasource:read`, `etl:read`, `cube:read`, `pivot:read`, `pivot:save`, `lineage:read`, `nl2sql:execute` | 피벗 분석/저장/조회 |
| **VIEWER** | `datasource:read`, `etl:read`, `cube:read`, `pivot:read`, `lineage:read` | 읽기 전용 |

#### Capability 전체 목록

| Capability | 설명 |
|-----------|------|
| `datasource:read` | 데이터소스 목록/상세 조회 |
| `datasource:write` | 데이터소스 생성/수정/삭제 |
| `etl:read` | ETL 파이프라인/실행 이력 조회 |
| `etl:edit` | ETL 파이프라인 생성/수정/삭제 |
| `etl:run` | ETL 파이프라인 실행/중단 |
| `cube:read` | 큐브/모델/차원/팩트 조회 |
| `cube:write` | 큐브/모델/차원/팩트 생성/수정 |
| `cube:publish` | 큐브 게시 (DRAFT → PUBLISHED) |
| `mondrian:edit` | Mondrian XML 편집 |
| `mondrian:deploy` | Mondrian XML 배포 |
| `pivot:read` | 피벗 뷰 조회 |
| `pivot:save` | 피벗 뷰 저장/공유 |
| `lineage:read` | 리니지 조회 |
| `ai:read` | AI 생성 결과 조회 |
| `ai:generate` | AI 큐브/DDL/샘플 생성 요청 |
| `nl2sql:execute` | NL2SQL 질의 실행 |

#### FastAPI 권한 체크 의존성

```python
from functools import wraps
from fastapi import HTTPException


def require_capability(*capabilities: str):
    """
    요청 컨텍스트의 역할이 필요한 capability를 충족하는지 검증한다.
    """
    async def checker(ctx: RequestContext = Depends(get_request_context)):
        user_capabilities = resolve_capabilities(ctx.roles)
        for cap in capabilities:
            if cap not in user_capabilities:
                raise HTTPException(
                    status_code=403,
                    detail=f"권한이 부족합니다: {cap} capability가 필요합니다."
                )
        return ctx
    return checker


# 사용 예시:
@router.post("/cubes/{cube_id}/publish")
async def publish_cube(
    cube_id: str,
    ctx: RequestContext = Depends(require_capability("cube:publish")),
):
    ...
```

### 7.4 FastAPI 적용 포인트

#### 미들웨어

| 미들웨어 | 순서 | 역할 |
|---------|------|------|
| `RequestIdMiddleware` | 1 | `X-Request-Id` 미존재 시 생성, 응답 헤더에도 포함 |
| `TraceIdMiddleware` | 2 | `X-Trace-Id` 전파, 로그에 trace_id 포함 |
| `ContextMiddleware` | 3 | `X-Tenant-Id`, `X-Project-Id` 등 헤더를 파싱하여 contextvars에 저장 |
| `ErrorFormatMiddleware` | 4 | 예외를 Axiom 표준 에러 포맷으로 변환 |
| `AuditLogMiddleware` | 5 | 쓰기 요청(POST/PUT/DELETE)의 감사 로그 기록 |

#### 의존성 주입

| 의존성 | 용도 |
|--------|------|
| `get_request_context()` | 요청 컨텍스트 추출 (7.1절 참고) |
| `require_capability("cube:publish")` | 권한 체크 (7.3절 참고) |
| `get_db_session()` | AsyncSession 획득 |
| `get_redis_client()` | Redis 클라이언트 획득 |

#### 서비스 계층 규칙

1. **Repository 호출 전** 반드시 `ctx.tenant_id`와 `ctx.project_id`로 scope 강제.
2. **이벤트 발행 시** Outbox 레코드에 `tenant_id`, `project_id`, `trace_id`를 자동 포함하는 envelope 헬퍼 사용.
3. **감사 대상 액션** 수행 시 audit_log 테이블에 기록 (7.5절 참고).

### 7.5 감사 로그 대상

#### 감사 대상 액션 목록

| # | 액션 | 대상 유형 | 설명 |
|---|------|----------|------|
| 1 | 데이터소스 생성 | `DATA_SOURCE` | 새 연결 정보 등록 |
| 2 | 데이터소스 수정 | `DATA_SOURCE` | 연결 정보 변경 |
| 3 | 데이터소스 삭제 | `DATA_SOURCE` | 소프트 삭제 |
| 4 | 큐브 게시 | `CUBE` | DRAFT → PUBLISHED 상태 전환 |
| 5 | Mondrian XML 배포 | `MONDRIAN_DOCUMENT` | XML 문서 운영 환경 배포 |
| 6 | ETL 실행 | `ETL_RUN` | 파이프라인 실행 트리거 |
| 7 | ETL 중단 | `ETL_RUN` | 실행 중인 파이프라인 취소 |
| 8 | Airflow DAG 배포 | `AIRFLOW_DAG` | ETL → DAG 변환 및 배포 |
| 9 | AI 생성 승인 | `AI_GENERATION` | AI 생성 결과 승인 |
| 10 | AI 생성 반려 | `AI_GENERATION` | AI 생성 결과 반려 |

#### 감사 로그 레코드 구조

```json
{
  "actor": "user-123-456",
  "actorName": "홍길동",
  "action": "CUBE_PUBLISHED",
  "targetType": "CUBE",
  "targetId": "cube-880e1700-uuid",
  "tenantId": "tenant-a1b2c3d4",
  "projectId": "project-p1p2p3p4",
  "before": {
    "cube_status": "VALIDATED",
    "version_no": 2
  },
  "after": {
    "cube_status": "PUBLISHED",
    "version_no": 3,
    "published_at": "2026-03-21T16:00:00Z"
  },
  "occurredAt": "2026-03-21T16:00:00Z",
  "traceId": "trace-cube-pub-001",
  "requestId": "req-550e8400"
}
```

---

## 8. 단계별 마이그레이션 계획

### Phase 0: 사전 정리 (1주)

**목표:** KAIR `data-platform-olap` 코드베이스의 구조를 파악하고, 핵심 도메인 모델을 식별하며, 파일 저장/환경 설정/외부 의존성 목록을 작성한다.

**작업 항목:**

| # | 작업 | 상세 | 산출물 |
|---|------|------|--------|
| 1 | 모듈 맵 작성 | KAIR olap 디렉토리 구조, 파일별 책임 정리 | `docs/kair-olap-module-map.md` |
| 2 | API 목록 추출 | 기존 REST API 엔드포인트, 요청/응답 스키마 | `docs/kair-olap-api-inventory.md` |
| 3 | DB/파일/Neo4j 사용 현황 | 어떤 데이터가 어디에 저장되는지 (JSON 파일 vs DB vs Neo4j) | 현황 표 |
| 4 | Vue 화면 목록 | 기존 프론트엔드 화면, 컴포넌트, 상태 관리 구조 | 화면 인벤토리 |
| 5 | 외부 의존성 분석 | Airflow, LLM, 기타 외부 서비스 연동 인터페이스 | 의존성 맵 |
| 6 | 리스크 식별 | 데이터 마이그레이션 난이도, 기능 공백, 기술 부채 | 리스크 레지스터 |

**산출물:** 모듈 맵, API 목록, DB/파일/Neo4j 사용 현황, Vue 화면 목록, 외부 의존성 맵, 리스크 레지스터

**완료 기준:** 팀 리뷰 통과, 이후 Phase의 작업량 추정 가능

---

### Phase 1: 백엔드 Lift-and-Shift (2주)

**목표:** `services/olap-studio`로 FastAPI 애플리케이션을 수용하고, docker-compose에 등록하며, PostgreSQL/Neo4j/Redis 연결과 health check가 동작하는 상태를 만든다.

**작업 항목:**

| # | 작업 | 상세 |
|---|------|------|
| 1 | 디렉토리 생성 | `services/olap-studio/` 디렉토리 및 기본 파일 구조 생성 |
| 2 | 기존 config 정리 | KAIR의 환경 설정을 Axiom 표준(`pydantic-settings` 기반)으로 변환 |
| 3 | docker-compose 등록 | `olap-studio-svc` 서비스 추가 (port 9005:8005) |
| 4 | init-db-schemas.sql 수정 | `CREATE SCHEMA IF NOT EXISTS olap;` 추가 |
| 5 | main.py 구성 | FastAPI 앱, 미들웨어, 라우터 등록 |
| 6 | health 엔드포인트 | `/health/live`, `/health/ready`, `/health/metrics` 구현 |
| 7 | 기존 API 포팅 | KAIR의 주요 API를 FastAPI 라우터로 옮기기 (기능 동작 우선, 리팩터링은 나중) |
| 8 | 의존성 설치 | `requirements.txt` / `pyproject.toml` 정리 |
| 9 | smoke test | 기존 API 주요 흐름의 수동/자동 smoke test 작성 |

**docker-compose 추가 항목:**

```yaml
olap-studio-svc:
  build:
    context: ./services/olap-studio
    dockerfile: Dockerfile
  ports:
    - "9005:8005"
  environment:
    - DATABASE_URL=postgresql+asyncpg://arkos:arkos@postgres-db:5432/insolvency_os
    - DATABASE_SCHEMA=olap
    - REDIS_URL=redis://redis-bus:6379
    - NEO4J_URI=bolt://neo4j-db:7687
    - NEO4J_USER=neo4j
    - NEO4J_PASSWORD=password
    - AIRFLOW_BASE_URL=http://airflow:8080
    - AIRFLOW_API_TOKEN=dev-airflow-token
    - LLM_MODEL=gpt-4o
    - JWT_SECRET_KEY=axiom-dev-secret-key-do-not-use-in-production
  depends_on:
    postgres-db:
      condition: service_healthy
    redis-bus:
      condition: service_healthy
  healthcheck:
    test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8005/health/live')\" || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 15s
```

**완료 기준:**
- 로컬/개발 환경에서 `docker-compose up olap-studio-svc` 정상 기동
- `/health/live` → 200 OK, `/health/ready` → 200 OK (DB/Redis 연결 확인)
- 기존 API 주요 흐름 smoke test 통과 (최소 3개 시나리오)

---

### Phase 2: 인증/멀티테넌트 적용 (1주)

**목표:** JWT/Gateway 기반 사용자 컨텍스트를 연결하고, tenant/project scope를 모든 데이터 접근에 강제한다.

**작업 항목:**

| # | 작업 | 상세 |
|---|------|------|
| 1 | RequestContext 모델 | `core/context.py` — 7.1절의 `RequestContext` 구현 |
| 2 | 헤더 파싱 미들웨어 | `ContextMiddleware` — Gateway 헤더 파싱 |
| 3 | 의존성 함수 | `get_request_context()`, `require_capability()` 구현 |
| 4 | 역할-Capability 매핑 | 7.3절의 매핑 테이블을 코드로 구현 |
| 5 | Repository scope 적용 | 모든 Repository 메서드에 `tenant_id + project_id` WHERE 조건 추가 |
| 6 | 에러 포맷 미들웨어 | Axiom 표준 에러 응답 포맷 (`ErrorFormatMiddleware`) |
| 7 | 통합 테스트 | 무권한 접근 차단, 다른 tenant 데이터 격리 테스트 |

**완료 기준:**
- 헤더 없는 요청 → 400 Bad Request
- `X-Roles: viewer`로 `POST /cubes/{id}/publish` → 403 Forbidden
- tenant A의 큐브가 tenant B 컨텍스트에서 조회되지 않음
- 통합 테스트 전체 통과

---

### Phase 3: 저장소 마이그레이션 (2주)

**목표:** JSON 파일 기반 저장을 제거하고 PostgreSQL `olap` 스키마를 도입한다.

**작업 항목:**

| # | 작업 | 상세 |
|---|------|------|
| 1 | DDL 실행 | 3장의 모든 CREATE TABLE 실행 (Alembic 초기 마이그레이션) |
| 2 | SQLAlchemy 모델 | `db/models.py` — ORM 모델 정의 |
| 3 | Repository 리팩터링 | 파일 I/O → asyncpg/SQLAlchemy 비동기 쿼리로 전환 |
| 4 | Alembic 설정 | `db/migrations/` — 마이그레이션 인프라 구성 |
| 5 | 데이터 import 도구 | 기존 JSON 파일 → PostgreSQL 일괄 import 스크립트 |
| 6 | 인덱스/제약조건 검증 | 3장의 인덱스가 모두 생성되었는지 확인 |
| 7 | 성능 테스트 | 큐브 조회, 피벗 실행, ETL 이력 조회의 응답 시간 측정 |

**완료 기준:**
- 큐브/ETL/Mondrian/피벗 저장 기능이 DB 기반으로 전환됨
- 기존 JSON 파일 의존 코드 0건 (grep 검증)
- Alembic `upgrade head` → `downgrade base` → `upgrade head` 왕복 성공
- 기존 파일 데이터 import 후 기능 동작 검증

---

### Phase 4: 이벤트/리니지 표준화 (1.5주)

**목표:** Transactional Outbox 기반 이벤트 발행을 구현하고, lineage 갱신 흐름을 정착시킨다.

**작업 항목:**

| # | 작업 | 상세 |
|---|------|------|
| 1 | outbox 테이블 | `olap.outbox_events` 테이블 생성 (3.8절) |
| 2 | EventPublisher | `events/publisher.py` — Outbox에 이벤트 저장하는 서비스 |
| 3 | RelayWorker | `events/relay_worker.py` — Outbox → Redis Streams 릴레이 워커 |
| 4 | 이벤트 우선 도입 | `olap.etl.run.completed`, `olap.cube.published`, `olap.lineage.updated` 3개 우선 |
| 5 | Synapse 소비자 | Synapse에 `olap.lineage.updated` 이벤트 소비자 추가 (Neo4j 동기화) |
| 6 | Canvas 알림 연동 | ETL 완료/실패 이벤트를 Canvas 알림으로 전달 |
| 7 | 이벤트 재처리 | 실패한 이벤트의 재처리 메커니즘 (retry count, dead letter) |

**완료 기준:**
- ETL 실행 완료 시 `olap.etl.run.completed` 이벤트가 Redis Streams에 발행됨
- 큐브 게시 시 `olap.cube.published` 이벤트가 발행됨
- Synapse가 `olap.lineage.updated` 이벤트를 소비하여 Neo4j에 노드/관계 생성
- 재처리 가능한 이벤트 인프라 검증 (수동 재발행 → 정상 처리)

---

### Phase 5: React 프론트 1차 이식 (3주)

**목표:** 데이터소스 / ETL / 큐브 관리 화면을 React로 이식한다. 상태/폼 중심 화면으로 이식 난이도가 낮다.

**작업 항목:**

| # | 작업 | 상세 | 기간 |
|---|------|------|------|
| 1 | routes.ts 확장 | OLAP Studio 관련 라우트 상수 추가 | 0.5일 |
| 2 | routeConfig.tsx 등록 | Lazy import 페이지 등록 | 0.5일 |
| 3 | 사이드바 메뉴 추가 | "OLAP Studio", "ETL", "큐브 관리", "데이터 소스" 메뉴 항목 | 0.5일 |
| 4 | API 클라이언트 | `features/*/api/` — OLAP Studio API 호출 함수 (TanStack Query) | 2일 |
| 5 | `/data/sources` 구현 | DataSourceListPage, DataSourceForm, ConnectionTestPanel, SchemaBrowser | 4일 |
| 6 | `/data/etl` 구현 | EtlPipelineListPage, EtlPipelineEditor, EtlRunHistoryTable, AirflowSyncPanel | 5일 |
| 7 | `/data/cubes` 구현 | CubeManagementPage, StarSchemaDiagram, 각종 Editor, MondrianXmlEditor | 5일 |
| 8 | 공통 컴포넌트 | 상태 뱃지, 타입 아이콘, 포맷터 등 공통 UI | 1일 |
| 9 | i18n | 한/영 번역 키 추가 | 1일 |

**완료 기준:**
- Vue 없이도 데이터소스/ETL/큐브 핵심 관리 기능 사용 가능
- 데이터소스 연결 테스트, ETL 실행, 큐브 게시 시나리오 동작
- 모든 새 페이지에 로딩/에러/빈 상태 처리 완료

---

### Phase 6: React 피벗 UI 이식 (3주)

**목표:** `/analysis/olap-studio` 피벗 분석 UI를 React로 이식한다. 드래그 앤 드롭, 결과 그리드, SQL 미리보기를 포함한다.

**작업 항목:**

| # | 작업 | 상세 | 기간 |
|---|------|------|------|
| 1 | PivotCanvas | 드래그 앤 드롭 Pivot Builder (`@dnd-kit/core` 사용, Vue `vuedraggable` 대체) | 5일 |
| 2 | PivotResultGrid | TanStack Table 기반 결과 그리드 (소계/합계, 셀 포맷팅) | 4일 |
| 3 | PivotSqlPreview | Monaco Editor 읽기 전용 SQL 뷰 | 1일 |
| 4 | CubeSelector | 큐브/뷰 목록 패널 | 2일 |
| 5 | 필터/차원/측정값 패널 | DimensionPanel, MeasurePanel (우측 패널) | 3일 |
| 6 | 저장/공유 기능 | Pivot View CRUD + 공유 | 2일 |
| 7 | 실행 로그 탭 | 실행 이력 하단 탭 | 1일 |
| 8 | 통합 테스트 | E2E 피벗 시나리오 (큐브 선택 → 드래그 → 실행 → 결과 확인) | 2일 |

**완료 기준:**
- 주요 피벗 시나리오(큐브 선택 → 차원 배치 → 실행 → 결과 확인 → 저장) 정상 동작
- Vision의 온톨로지 피벗(`/analysis/olap`)과 독립 메뉴로 동작
- 드래그 앤 드롭이 데스크톱 브라우저에서 안정적으로 동작

---

### Phase 7: Airflow/NL2SQL/AI 기능 고도화 (2주)

**목표:** Airflow DAG 배포 연계를 안정화하고, 탐색형 NL2SQL과 AI 큐브 생성 보조 기능을 도입한다.

**작업 항목:**

| # | 작업 | 상세 | 기간 |
|---|------|------|------|
| 1 | Airflow 클라이언트 안정화 | Airflow REST API 연동, 재시도, 타임아웃 처리 | 3일 |
| 2 | DAG sync status UI | ETL 화면에 Airflow 동기화 상태 패널 | 2일 |
| 3 | 탐색형 NL2SQL 백엔드 | 큐브 메타데이터 컨텍스트 기반 LLM 프롬프트 + SQL 생성 + 실행 | 3일 |
| 4 | NL2SQL UI | 채팅형 인터페이스 + 결과 표시 + 이력 | 3일 |
| 5 | AI 큐브 생성 백엔드 | 테이블 분석 → LLM 큐브 초안 → 사용자 검토 흐름 | 2일 |
| 6 | AI 생성 UI | AiCubeGenerationPanel (큐브 관리 탭) | 1일 |

**완료 기준:**
- Airflow DAG 배포/트리거/상태 조회가 안정적으로 동작
- 탐색형 NL2SQL로 큐브 컨텍스트 내 자연어 질의 → SQL 변환 → 결과 확인 가능
- AI 큐브 생성 → 사용자 검토 → 승인/반려 워크플로 동작
- 운영 가능한 수준의 탐색형 데이터 워크스페이스 완성

---

### Phase 8: 기존 서비스 연계 고도화 (2주)

**목표:** Vision/Oracle/Synapse/Weaver와 조회·링크·이벤트 수준의 연계를 구현한다. 기능 소유권은 유지하면서 사용자 경험을 통합한다.

**작업 항목:**

| # | 작업 | 상세 | 기간 |
|---|------|------|------|
| 1 | Vision 연계 | Vision에서 OLAP Studio 큐브 메타데이터를 참조하는 API 어댑터 | 2일 |
| 2 | Oracle 연계 | Oracle NL2SQL에서 큐브 metadata adapter (피벗 질의 자동 컨텍스트 추가) | 2일 |
| 3 | Synapse 연계 | Synapse 리니지 뷰에서 OLAP Studio lineage 엔티티로의 deep-link | 2일 |
| 4 | Weaver 연계 | Weaver 카탈로그에 큐브/ETL 요약 메타데이터 동기화 (이벤트 기반) | 2일 |
| 5 | Vision cube_manager 폐기 | Vision의 `cube_manager.py`, `etl_manager.py`를 OLAP Studio API 호출로 대체 | 2일 |
| 6 | 교차 링크 UI | 각 화면 간 교차 네비게이션 링크 구현 | 1일 |
| 7 | 통합 E2E 테스트 | 전체 연계 시나리오 E2E 검증 | 1일 |

**완료 기준:**
- Vision에서 OLAP Studio 큐브 메타데이터 참조 가능
- Synapse 리니지 뷰에서 OLAP Studio lineage 노드로 deep-link 동작
- Weaver 카탈로그에 큐브/ETL 요약 자동 반영
- Vision의 `cube_manager.py`, `etl_manager.py` 제거, OLAP Studio API 위임으로 전환

---

### 전체 일정 요약

| Phase | 기간 | 목표 | 의존성 |
|-------|------|------|--------|
| Phase 0 | 1주 | 사전 정리 | 없음 |
| Phase 1 | 2주 | 백엔드 Lift-and-Shift | Phase 0 |
| Phase 2 | 1주 | 인증/멀티테넌트 | Phase 1 |
| Phase 3 | 2주 | 저장소 마이그레이션 | Phase 1 |
| Phase 4 | 1.5주 | 이벤트/리니지 표준화 | Phase 3 |
| Phase 5 | 3주 | React 프론트 1차 | Phase 2, Phase 3 |
| Phase 6 | 3주 | React 피벗 UI | Phase 5 |
| Phase 7 | 2주 | Airflow/NL2SQL/AI | Phase 4, Phase 6 |
| Phase 8 | 2주 | 기존 서비스 연계 | Phase 7 |
| **합계** | **약 17.5주** | | |

> Phase 2와 Phase 3은 병렬 진행 가능 (각각 인증과 저장소에 집중). Phase 5는 Phase 2 + Phase 3 모두 완료 후 시작.

---

## 9. API 영역 초안

### 9.1 데이터소스

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/data-sources` | 데이터소스 목록 조회 | `datasource:read` |
| `POST` | `/data-sources` | 데이터소스 생성 | `datasource:write` |
| `GET` | `/data-sources/{id}` | 데이터소스 상세 조회 | `datasource:read` |
| `PUT` | `/data-sources/{id}` | 데이터소스 수정 | `datasource:write` |
| `DELETE` | `/data-sources/{id}` | 데이터소스 삭제 (소프트) | `datasource:write` |
| `POST` | `/data-sources/{id}/test` | 연결 테스트 | `datasource:read` |
| `GET` | `/data-sources/{id}/schema` | 스키마 인트로스펙션 | `datasource:read` |

### 9.2 모델/스타 스키마

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/models` | 모델 목록 조회 | `cube:read` |
| `POST` | `/models` | 모델 생성 | `cube:write` |
| `GET` | `/models/{id}` | 모델 상세 조회 | `cube:read` |
| `PUT` | `/models/{id}` | 모델 수정 | `cube:write` |
| `DELETE` | `/models/{id}` | 모델 삭제 (소프트) | `cube:write` |
| `POST` | `/models/{id}/dimensions` | 차원 추가 | `cube:write` |
| `PUT` | `/models/{id}/dimensions/{dimId}` | 차원 수정 | `cube:write` |
| `DELETE` | `/models/{id}/dimensions/{dimId}` | 차원 삭제 | `cube:write` |
| `POST` | `/models/{id}/facts` | 팩트 추가 | `cube:write` |
| `PUT` | `/models/{id}/facts/{factId}` | 팩트 수정 | `cube:write` |
| `DELETE` | `/models/{id}/facts/{factId}` | 팩트 삭제 | `cube:write` |
| `POST` | `/models/{id}/joins` | 조인 추가 | `cube:write` |
| `DELETE` | `/models/{id}/joins/{joinId}` | 조인 삭제 | `cube:write` |

### 9.3 큐브

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/cubes` | 큐브 목록 조회 | `cube:read` |
| `POST` | `/cubes` | 큐브 생성 | `cube:write` |
| `GET` | `/cubes/{id}` | 큐브 상세 조회 | `cube:read` |
| `PUT` | `/cubes/{id}` | 큐브 수정 | `cube:write` |
| `DELETE` | `/cubes/{id}` | 큐브 삭제 (소프트) | `cube:write` |
| `POST` | `/cubes/{id}/validate` | 큐브 검증 | `cube:write` |
| `POST` | `/cubes/{id}/publish` | 큐브 게시 | `cube:publish` |
| `GET` | `/cubes/{id}/dimensions` | 큐브 차원 목록 | `cube:read` |
| `POST` | `/cubes/{id}/dimensions` | 큐브 차원 추가 | `cube:write` |
| `GET` | `/cubes/{id}/measures` | 큐브 측정값 목록 | `cube:read` |
| `POST` | `/cubes/{id}/measures` | 큐브 측정값 추가 | `cube:write` |

### 9.4 Mondrian

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/mondrian/{cubeId}` | 최신 Mondrian XML 조회 | `cube:read` |
| `POST` | `/mondrian/{cubeId}/generate` | 큐브 정의 → XML 자동 생성 | `mondrian:edit` |
| `POST` | `/mondrian/{cubeId}/validate` | XML 검증 (XSD + 의미 규칙) | `mondrian:edit` |
| `POST` | `/mondrian/{cubeId}/deploy` | XML 배포 | `mondrian:deploy` |
| `GET` | `/mondrian/{cubeId}/history` | XML 버전 이력 | `cube:read` |

### 9.5 피벗

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `POST` | `/pivot/execute` | 피벗 질의 실행 | `pivot:read` |
| `POST` | `/pivot/preview-sql` | 피벗 → SQL 미리보기 (실행 없이) | `pivot:read` |
| `GET` | `/pivot/views` | 저장된 Pivot View 목록 | `pivot:read` |
| `POST` | `/pivot/views` | Pivot View 저장 | `pivot:save` |
| `GET` | `/pivot/views/{id}` | Pivot View 상세 | `pivot:read` |
| `PUT` | `/pivot/views/{id}` | Pivot View 수정 | `pivot:save` |
| `DELETE` | `/pivot/views/{id}` | Pivot View 삭제 | `pivot:save` |
| `POST` | `/pivot/views/{id}/share` | Pivot View 공유 | `pivot:save` |

### 9.6 ETL

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/etl/pipelines` | 파이프라인 목록 | `etl:read` |
| `POST` | `/etl/pipelines` | 파이프라인 생성 | `etl:edit` |
| `GET` | `/etl/pipelines/{id}` | 파이프라인 상세 | `etl:read` |
| `PUT` | `/etl/pipelines/{id}` | 파이프라인 수정 | `etl:edit` |
| `DELETE` | `/etl/pipelines/{id}` | 파이프라인 삭제 (소프트) | `etl:edit` |
| `POST` | `/etl/pipelines/{id}/run` | 파이프라인 실행 | `etl:run` |
| `GET` | `/etl/pipelines/{id}/runs` | 파이프라인 실행 이력 | `etl:read` |
| `GET` | `/etl/runs/{id}` | 실행 상세 | `etl:read` |
| `GET` | `/etl/runs/{id}/steps` | 실행 단계별 상태 | `etl:read` |
| `POST` | `/etl/pipelines/{id}/deploy-airflow` | Airflow DAG 배포 | `etl:edit` |

### 9.7 Airflow

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/airflow/dags` | 등록된 DAG 목록 | `etl:read` |
| `POST` | `/airflow/dag/generate` | 파이프라인 → DAG 코드 생성 | `etl:edit` |
| `POST` | `/airflow/dag/{dagId}/trigger` | DAG 수동 트리거 | `etl:run` |
| `GET` | `/airflow/dag/{dagId}/status` | DAG 현재 상태 | `etl:read` |
| `GET` | `/airflow/dag/{dagId}/runs` | DAG 실행 이력 | `etl:read` |

### 9.8 리니지

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/lineage/entities` | 엔티티 목록 (필터: entity_type) | `lineage:read` |
| `GET` | `/lineage/entities/{id}` | 엔티티 상세 | `lineage:read` |
| `GET` | `/lineage/graph` | 리니지 그래프 (엔티티 + 엣지) | `lineage:read` |
| `GET` | `/lineage/impact/{entityId}` | 영향 분석 (upstream + downstream) | `lineage:read` |
| `POST` | `/lineage/refresh` | 리니지 수동 갱신 | `etl:edit` |

### 9.9 AI

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `POST` | `/ai/cubes/generate` | AI 큐브 자동 생성 | `ai:generate` |
| `POST` | `/ai/ddl/generate` | AI DDL 생성 | `ai:generate` |
| `POST` | `/ai/sample-data/generate` | AI 샘플 데이터 생성 | `ai:generate` |
| `POST` | `/ai/mapping/suggest` | AI 컬럼 매핑 제안 | `ai:generate` |
| `GET` | `/ai/generations` | AI 생성 이력 | `ai:read` |
| `GET` | `/ai/generations/{id}` | AI 생성 상세 | `ai:read` |
| `POST` | `/ai/generations/{id}/approve` | AI 생성 결과 승인 | `cube:publish` |
| `POST` | `/ai/generations/{id}/reject` | AI 생성 결과 반려 | `cube:write` |

### 9.10 NL2SQL (탐색형)

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `POST` | `/nl2sql/generate` | 자연어 → SQL 변환 (실행 없이) | `nl2sql:execute` |
| `POST` | `/nl2sql/execute` | 자연어 → SQL 변환 + 실행 | `nl2sql:execute` |
| `POST` | `/nl2sql/preview` | SQL 미리보기 + 실행 계획 | `nl2sql:execute` |
| `GET` | `/nl2sql/history` | NL2SQL 질의 이력 | `nl2sql:execute` |

### 9.11 헬스체크

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/health/live` | 서비스 생존 확인 | 없음 (공개) |
| `GET` | `/health/ready` | DB/Redis/Airflow 연결 상태 | 없음 (공개) |
| `GET` | `/health/metrics` | Prometheus 메트릭 | 없음 (내부) |

---

## 10. 최종 의사결정 요약

### 최종안

KAIR `data-platform-olap`은 **OLAP Studio**라는 독립 마이크로서비스(`services/olap-studio`, port 9005)로 Axiom 생태계에 수용한다.

### Axiom 공통 표준 적용 항목

| # | 항목 | 적용 방법 |
|---|------|----------|
| 1 | **인증/JWT** | Gateway에서 JWT 검증, 내부 헤더 전달 (7.1절) |
| 2 | **Tenant/Project 컨텍스트** | `X-Tenant-Id`, `X-Project-Id` 헤더 기반, 모든 쿼리에 scope 강제 (7.2절) |
| 3 | **Gateway 라우팅** | `/api/gateway/olap/**` → `olap-studio:8005/**` (5.1절) |
| 4 | **감사 로그** | 10개 주요 액션에 대한 감사 로그 기록 (7.5절) |
| 5 | **이벤트 계약** | Redis Streams + Transactional Outbox, 7개 이벤트 유형 (4장) |
| 6 | **프론트 메뉴/UX** | Canvas React SPA 통합, 7개 메뉴 항목 (6.1절) |

### 핵심 이유

#### 이유 1: 강결합된 메타모델의 단일 소유

스타 스키마(Model → Dimension/Fact/Join) → 큐브(Cube → CubeDimension/CubeMeasure) → Mondrian XML → ETL 파이프라인 → 리니지는 하나의 **메타모델 체인**을 형성한다. 이 체인의 어느 한 부분을 변경하면 나머지도 연쇄적으로 영향을 받는다. 이를 여러 서비스에 분산하면 변경 시 서비스 간 조율이 필요해지고, 데이터 정합성 보장이 어려워진다.

#### 이유 2: C안(기능 분산)의 높은 운영 복잡도

C안(기능 분산 — 큐브는 Vision, ETL은 Weaver, 리니지는 Synapse 등)은 서비스 수는 늘어나지 않지만, 각 서비스의 책임 범위가 넓어지고, 변경 경로가 복잡해진다. 특히 ETL → 큐브 → 리니지 연쇄 흐름에서 3개 서비스를 조율해야 하는 트랜잭션 복잡도가 크게 증가한다.

#### 이유 3: 예측 가능한 이식 비용

B안은 KAIR의 기존 코드를 하나의 서비스에 담아 점진적으로 개선하는 방식이다. Phase별 작업량이 명확하고, 각 Phase의 완료 기준이 독립적이어서 진행 상황 추적이 용이하다. 전체 약 17.5주의 일정이 예측 가능하다.

#### 이유 4: 향후 확장 유연성

독립 서비스로 분리되어 있으므로, 향후 OLAP Studio를 별도 제품으로 분리하거나, 전용 인프라(GPU, 대용량 스토리지 등)로 확장하거나, 팀 단위로 독립적으로 운영하는 것이 가능하다.

### 실행 우선순위

| 순위 | 단계 | 핵심 목표 | 예상 기간 |
|------|------|----------|----------|
| 1 | `services/olap-studio` 백엔드 수용 | 서비스 기동 + smoke test | 2주 |
| 2 | JWT / X-Tenant-Id / X-Project-Id 적용 | 보안 + 멀티테넌트 격리 | 1주 |
| 3 | JSON 저장 제거 + PostgreSQL 스키마 도입 | 데이터 무결성 + 버전관리 | 2주 |
| 4 | Gateway `/api/gateway/olap/**` 추가 | 라우팅 통합 | Phase 1과 병행 |
| 5 | React `/data/sources`, `/data/etl`, `/data/cubes` 이식 | 관리 기능 사용 가능 | 3주 |
| 6 | `/analysis/olap-studio` 피벗 UI 이식 | 핵심 분석 기능 | 3주 |
| 7 | Airflow/NL2SQL/AI/lineage 고도화 | 전체 기능 완성 | 4주 |

---

> **이 문서는 OLAP Studio 통합의 설계 기준으로 사용하며, 실제 구현 과정에서 발견되는 기술적 제약이나 요구사항 변경에 따라 업데이트한다.**
