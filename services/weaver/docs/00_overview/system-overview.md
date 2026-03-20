# Axiom Weaver - 시스템 개요

<!-- affects: all modules -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

## 이 문서가 답하는 질문

- Axiom Weaver는 무엇인가?
- 왜 데이터 패브릭이 필요한가?
- 비즈니스 프로세스 인텔리전스에서 Weaver의 역할은 무엇인가?
- 어떤 데이터베이스를 지원하는가?

---

## 1. Weaver란 무엇인가

**Axiom Weaver**는 "흩어진 데이터를 하나의 직물(Fabric)로 짜내는 존재"이다.

엔터프라이즈 환경에서는 이해관계자, 대상 조직, 운영 데이터, 재무 데이터 등이 **서로 다른 데이터베이스와 시스템**에 분산되어 있다. Weaver는 이 분산된 데이터를 **단일 인터페이스**로 추상화하여, 사용자와 AI 에이전트가 마치 하나의 데이터베이스를 다루듯 접근할 수 있게 한다.

### 핵심 역할 (현재 구현 기준)

| 역할 | 설명 | 구현 상태 |
|------|------|----------|
| **데이터소스 관리** | 데이터소스 CRUD, 연결 테스트, 헬스 체크 | Implemented |
| **메타데이터 추출** | 스키마 인트로스펙션 SSE 스트리밍 (postgresql, mysql, oracle) | Implemented |
| **메타데이터 그래프** | 추출된 메타데이터를 Synapse(Neo4j) 그래프로 저장 | Implemented (metadata_external_mode) |
| **메타데이터 카탈로그** | 패브릭 스냅샷, 비즈니스 용어 사전(Glossary), 태그, diff | Implemented |
| **쿼리 실행** | MindsDB 경유 / 모의 데이터 실행, 물리화 테이블 | Implemented |
| **Insight 잡 스토어** | Redis 기반 비동기 분석 잡 (impact, subgraph), RLS 세션 | Implemented |
| **문서 수집** | 문서 업로드 + DDD 개념 추출 + Synapse 온톨로지 적용 파이프라인 | Implemented |
| **Outbox Relay** | 이벤트 소싱 — Transactional Outbox 패턴 + Redis Streams 전파 | Implemented |
| **다중 DB 추상화** | MindsDB 경유 (external_mode 활성화 시) | Implemented (조건부) |
| **ETL 파이프라인** | Apache Airflow 연동 | 미구현 |

---

## 2. 왜 데이터 패브릭이 필요한가

### 2.1 엔터프라이즈 데이터 현실

```
┌─ ERP 시스템 (PostgreSQL) ─────────────────────────────────┐
│  운영 정보, 비즈니스 프로세스, 조직 정보                      │
└────────────────────────────────────────────────────────────┘

┌─ 재무 시스템 (Oracle/MySQL) ──────────────────────────────┐
│  재무 정보, 거래 내역, 예산 데이터                           │
└────────────────────────────────────────────────────────────┘

┌─ CRM 시스템 (다양) ───────────────────────────────────────┐
│  고객 정보, 영업 활동, 계약 데이터                           │
└────────────────────────────────────────────────────────────┘

┌─ HR/회계 (ERP) ─────────────────────────────────────────┐
│  인사 정보, 급여 내역, 조직도                               │
└────────────────────────────────────────────────────────────┘
```

이 데이터들은 **서로 다른 DB 엔진, 서로 다른 스키마, 서로 다른 인증 체계**를 사용한다. 데이터 분석가가 "이 대상 조직의 전체 운영 현황을 보여줘"라고 요청하면, 종래에는 각 시스템에 개별 접속하여 수작업으로 데이터를 취합해야 했다.

### 2.2 Weaver의 해결 방식

```
사용자/AI 에이전트
       │
       ▼
┌─ Weaver API ──────────────────────────────────────────────┐
│  POST /api/query  →  "SELECT * FROM erp_db.운영현황         │
│                       JOIN finance_db.재무정보 ON ..."       │
└────────────┬──────────────────────────────────────────────┘
             │
             ▼
┌─ MindsDB Gateway ─────────────────────────────────────────┐
│  SQL 파싱 → 대상 DB 라우팅 → 결과 통합 → 반환               │
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐     │
│  │PostgreSQL│  │  MySQL  │  │ MongoDB │  │   Redis  │     │
│  └─────────┘  └─────────┘  └─────────┘  └──────────┘     │
└─────────────────────────────────────────────────────────────┘
```

**하나의 SQL 쿼리로 여러 DB의 데이터를 조인**할 수 있다. 이것이 데이터 패브릭의 핵심 가치이다.

---

## 3. 지원 데이터베이스 엔진

| 엔진 | 용도 (엔터프라이즈) | 메타데이터 추출 | 쿼리 실행 |
|------|-------------------|-----------------|----------|
| **PostgreSQL** | 운영 관리, ERP, 비즈니스 프로세스 | 지원 (어댑터) | 지원 |
| **MySQL** | 레거시 시스템, CRM | 지원 (어댑터) | 지원 |
| **Oracle** | 대형 엔터프라이즈 DB | 계획 (어댑터) | 지원 |
| **Neo4j** | 관계 그래프 (이해관계자-대상 조직-프로세스) | 지원 (그래프) | 지원 |
| **MongoDB** | 비정형 문서 (스캔 이미지, 계약서) | 미정 | 지원 |
| **Redis** | 캐시, 세션, 실시간 알림 | 해당 없음 | 지원 |
| **Elasticsearch** | 문서 전문 검색 | 미정 | 지원 |
| **Web** | 외부 API 연동 (공시 시스템 등) | 해당 없음 | 지원 |
| **OpenAI** | AI 모델 연동 (MindsDB ML 엔진) | 해당 없음 | 지원 |

---

## 4. Axiom 생태계에서의 위치

```
┌─────────────────────────────────────────────────────────────────┐
│                     Axiom 플랫폼 전체 구조                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Canvas  │  │  Oracle  │  │  Vision  │  │   Synapse    │   │
│  │ (UI)     │  │ (NL2SQL) │  │ (분석)   │  │ (온톨로지)   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │              │             │                │            │
│       │              │             │                │            │
│  ┌────▼──────────────▼─────────────▼────────────────▼───────┐   │
│  │                     Axiom Core (공통 기반)                │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │              ★ Axiom Weaver (데이터 패브릭) ★              │   │
│  │                                                           │   │
│  │  데이터소스 관리 │ 메타데이터 추출 │ 쿼리 실행 │ ETL      │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌──────┐  ┌──────┐  ┌───▼──┐  ┌──────┐  ┌──────┐  ┌──────┐  │
│  │  PG  │  │MySQL │  │Neo4j │  │Mongo │  │Redis │  │  ES  │  │
│  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘  │
└─────────────────────────────────────────────────────────────────┘
```

Weaver는 Axiom의 **데이터 인프라 계층**이다. Oracle(NL2SQL), Vision(분석), Synapse(온톨로지) 등 상위 모듈은 모두 Weaver를 통해 데이터에 접근한다.

---

## 5. 기술 스택

| 계층 | 기술 | 용도 |
|------|------|------|
| **웹 프레임워크** | FastAPI 1.0.0 | REST API 서버 |
| **비동기 서버** | Uvicorn | ASGI 서버 |
| **HTTP 클라이언트** | httpx | MindsDB/Synapse API 호출 |
| **데이터 패브릭** | MindsDB (external_mode) | 다중 DB 게이트웨이 (조건부 활성화) |
| **메타데이터 저장** | PostgreSQL (metadata_pg_mode) + Synapse/Neo4j (metadata_external_mode) | 3-tier 저장소 전략 |
| **Insight 캐시** | Redis (aioredis) | 잡 스토어, 캐시키, dedup |
| **PG 드라이버** | asyncpg | PostgreSQL 비동기 연결 (Insight, 메타데이터) |
| **스키마 인트로스펙션** | asyncpg / aiomysql / oracledb | 대상 DB 스키마 추출 |
| **인증** | python-jose (JWT HS256) | Core 발급 JWT 검증 + 서비스 토큰 |
| **데이터 검증** | Pydantic v2 | 요청/응답 모델 |
| **이벤트 소싱** | Transactional Outbox + Redis Streams | WeaverRelayWorker |
| **로깅** | Python logging + 비밀 리다크션 | 구조화 로깅 |
| **ETL** | Apache Airflow | 미구현 (향후 계획) |

---

## 6. 용어 사전

| 용어 | 정의 |
|------|------|
| **데이터 패브릭 (Data Fabric)** | 분산된 데이터 소스를 통합 인터페이스로 추상화하는 아키텍처 |
| **데이터소스 (DataSource)** | Weaver에 등록된 개별 데이터베이스 연결 |
| **스키마 인트로스펙션 (Schema Introspection)** | DB에 연결하여 스키마, 테이블, 컬럼, FK 관계를 자동 추출하는 과정 |
| **메타데이터 그래프** | Neo4j에 저장된 DataSource-Schema-Table-Column 계층 구조 |
| **MindsDB** | MySQL/PostgreSQL 호환 프로토콜로 다중 DB를 추상화하는 AI-DB 플랫폼 |
| **어댑터 (Adapter)** | 각 DB 엔진별 스키마 추출 구현체 (PostgreSQL, MySQL, Oracle) |
| **물리화 테이블 (Materialized Table)** | 쿼리 결과를 MindsDB 내 테이블로 영구 저장한 것 |
| **SSE (Server-Sent Events)** | 서버에서 클라이언트로 실시간 진행률을 전송하는 프로토콜 |
| **ETL** | Extract-Transform-Load. 데이터 수집/변환/적재 파이프라인 |
| **FK (Foreign Key)** | 외래 키. 테이블 간 참조 관계 |

---

## 7. K-AIR 이식 현황

Weaver는 K-AIR 프로젝트의 `robo-data-fabric-main` 저장소를 기반으로 이식된다.

| 항목 | K-AIR 원본 | Weaver 구현 | 상태 |
|------|-----------|-------------|------|
| 데이터소스 CRUD | `routers/datasources.py` | `api/datasource.py` | 완료 |
| 쿼리 실행 | `routers/query.py` | `api/query.py` | 완료 |
| MindsDB 클라이언트 | `services/mindsdb_service.py` | `services/mindsdb_client.py` | 완료 |
| Neo4j 메타데이터 | `services/neo4j_service.py` | `services/neo4j_metadata_store.py` | 완료 |
| PG 메타데이터 저장소 | (신규) | `services/postgres_metadata_store.py` | 완료 |
| 스키마 인트로스펙션 | `services/schema_introspection.py` | `core/schema_introspection.py` + `services/introspection_service.py` | 완료 |
| 메타데이터 카탈로그 | (신규) | `api/metadata_catalog.py` | 완료 |
| Insight 잡 스토어 | (신규) | `api/insight.py` + `services/insight_job_store.py` | 완료 |
| 문서 수집 | (신규) | `api/document_ingestion.py` | 완료 |
| Outbox Relay | (신규) | `events/outbox.py` | 완료 |
| Vue3 프론트엔드 | `frontend/` | 제외 (Canvas에서 재작성) | - |

### 이식 원칙

1. **백엔드 코드 직접 활용**: FastAPI 라우터/서비스 코드를 Axiom 구조에 맞게 재배치
2. **프론트엔드 제외**: Vue 3 UI는 Canvas(React 18)에서 재작성
3. **보안 강화**: K-AIR의 기술 부채(Neo4j 비밀번호 평문, CORS 전체 허용) 해결
4. **어댑터 확장**: Oracle 어댑터 신규 추가

---

## 8. 관련 문서

| 문서 | 위치 | 설명 |
|------|------|------|
| 아키텍처 개요 | `01_architecture/architecture-overview.md` | 전체 아키텍처와 컴포넌트 관계 |
| 데이터소스 API | `02_api/datasource-api.md` | 데이터소스 CRUD API 전체 스펙 |
| 쿼리 API | `02_api/query-api.md` | MindsDB 쿼리 실행 API |
| Neo4j 스키마 | `06_data/neo4j-schema.md` | 메타데이터 그래프 스키마 상세 |
| ADR-001 | `99_decisions/ADR-001-mindsdb-gateway.md` | MindsDB 선택 근거 |
| 메타데이터 서비스 아키텍처 | `01_architecture/metadata-service.md` | 메타데이터 서비스 전체 설계 |
| 패브릭 스냅샷 아키텍처 | `01_architecture/fabric-snapshot.md` | 패브릭 스냅샷 설계 |
| 메타데이터 변경 전파 | `03_backend/metadata-propagation.md` | 메타데이터 변경 전파 메커니즘 |
| ADR-004 | `99_decisions/ADR-004-metadata-service.md` | 메타데이터 서비스 격상 근거 |
