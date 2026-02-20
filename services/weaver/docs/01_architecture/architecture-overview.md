# Weaver 아키텍처 개요

<!-- affects: api, backend, data -->
<!-- requires-update: 02_api/datasource-api.md, 03_backend/service-structure.md -->

## 이 문서가 답하는 질문

- Weaver의 전체 아키텍처는 어떻게 구성되어 있는가?
- MindsDB는 어떻게 통합되는가?
- 각 컴포넌트의 경계와 책임은 무엇인가?
- 데이터 흐름은 어떻게 이루어지는가?

---

## 1. 전체 아키텍처

### 1.1 계층 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Axiom Canvas (React 18)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│  │ DataSources  │  │ QueryEditor  │  │ MetadataExplorer      │     │
│  │ 관리 화면    │  │ SQL 편집기   │  │ 스키마/테이블 브라우저 │     │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘     │
└─────────┼──────────────────┼─────────────────────┼─────────────────┘
          │ HTTP/REST        │ HTTP/REST            │ SSE
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Weaver API (FastAPI)                              │
│                                                                      │
│  ┌─ API Layer (Routers) ──────────────────────────────────────────┐ │
│  │                                                                 │ │
│  │  datasources.py          query.py           metadata.py        │ │
│  │  - CRUD 엔드포인트       - SQL 실행          - 스키마 추출     │ │
│  │  - 헬스체크              - 물리화 테이블      - SSE 스트리밍   │ │
│  │  - 연결 테스트           - ML 모델 조회       - 테이블/컬럼    │ │
│  │                                                                 │ │
│  └─────────────┬───────────────┬────────────────┬─────────────────┘ │
│                │               │                │                    │
│  ┌─ Service Layer ────────────┬┴────────────────┴──────────────────┐ │
│  │                            │                                    │ │
│  │  MindsDB Client           Neo4j Service      Schema             │ │
│  │  - HTTP API 통신          - 메타데이터 CRUD   Introspection     │ │
│  │  - 쿼리 실행              - 그래프 탐색       - PostgreSQL      │ │
│  │  - 연결 관리              - 관계 저장         - MySQL           │ │
│  │  - 타임아웃 제어                              - Oracle          │ │
│  │                                                                 │ │
│  └────────┬──────────────────┬───────────────────┬─────────────────┘ │
│           │                  │                   │                    │
└───────────┼──────────────────┼───────────────────┼────────────────────┘
            │                  │                   │
   ┌────────▼────────┐  ┌─────▼─────┐  ┌──────────▼──────────┐
   │    MindsDB       │  │   Neo4j   │  │   대상 DB들          │
   │                  │  │   5.0+    │  │                      │
   │  ┌────────────┐  │  │  메타     │  │  ┌──────┐ ┌──────┐  │
   │  │ PostgreSQL │  │  │  데이터   │  │  │  PG  │ │MySQL │  │
   │  │  핸들러    │  │  │  그래프   │  │  └──────┘ └──────┘  │
   │  ├────────────┤  │  │           │  │  ┌──────┐ ┌──────┐  │
   │  │ MySQL      │  │  └───────────┘  │  │Oracle│ │Mongo │  │
   │  │  핸들러    │  │                  │  └──────┘ └──────┘  │
   │  ├────────────┤  │                  │  ┌──────┐ ┌──────┐  │
   │  │ MongoDB    │  │                  │  │Redis │ │  ES  │  │
   │  │  핸들러    │  │                  │  └──────┘ └──────┘  │
   │  └────────────┘  │                  └─────────────────────┘
   └──────────────────┘
```

### 1.2 컴포넌트 책임 분리

| 컴포넌트 | 책임 | 경계 |
|----------|------|------|
| **API Layer** | HTTP 요청 처리, 입력 검증, 응답 직렬화 | 외부 클라이언트와의 인터페이스 |
| **MindsDB Client** | MindsDB HTTP API 통신, SQL 실행, 연결 관리 | MindsDB 서버와의 유일한 접점 |
| **Neo4j Service** | 메타데이터 그래프 CRUD, 관계 관리 | Neo4j와의 유일한 접점 |
| **Schema Introspection** | DB별 스키마 추출 (어댑터 패턴) | 대상 DB와의 직접 연결 |

---

## 2. MindsDB 통합 아키텍처

### 2.1 MindsDB가 하는 일

MindsDB는 Weaver의 **데이터 패브릭 게이트웨이** 역할을 한다.

```
┌─ Weaver ───────────────────────────────────────┐
│                                                 │
│  POST /api/query                                │
│  Body: { "sql": "SELECT * FROM erp_db.users     │
│           JOIN crm_db.orders ON ..." }          │
│                                                 │
│  ┌─ MindsDB Client ──────────────────────────┐ │
│  │                                            │ │
│  │  1. SQL을 MindsDB HTTP API로 전달          │ │
│  │  2. MindsDB가 SQL 파싱                     │ │
│  │  3. 대상 DB별로 서브쿼리 분배              │ │
│  │  4. 각 DB에서 결과 수집                    │ │
│  │  5. 결과 통합하여 반환                     │ │
│  │                                            │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 2.2 MindsDB HTTP API 연동

```python
# MindsDB HTTP API 호출 구조
class MindsDBClient:
    base_url: str = "http://localhost:47334"
    api_endpoint: str = "/api/sql/query"
    timeout: int = 120  # seconds

    async def execute_query(self, sql: str) -> dict:
        """MindsDB SQL API로 쿼리 실행"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}{self.api_endpoint}",
                json={"query": sql}
            )
            return response.json()
```

### 2.3 MindsDB 데이터소스 등록 흐름

```
사용자가 데이터소스 생성 요청
         │
         ▼
┌─ Weaver API ────────────────────────────────────────────┐
│  POST /api/datasources                                   │
│  Body: {                                                 │
│    "name": "erp_db",                                     │
│    "engine": "postgresql",                               │
│    "connection": {                                       │
│      "host": "erp-db.internal",                          │
│      "port": 5432,                                       │
│      "database": "enterprise_ops",                       │
│      "user": "reader",                                   │
│      "password": "encrypted_password"                    │
│    }                                                     │
│  }                                                       │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─ 처리 순서 ─────────────────────────────────────────────┐
│                                                          │
│  1. Pydantic 모델로 입력 검증                             │
│  2. MindsDB에 CREATE DATABASE 실행                       │
│     → "CREATE DATABASE erp_db                            │
│        ENGINE = 'postgresql'                             │
│        PARAMETERS = {...}"                               │
│  3. Neo4j에 :DataSource 노드 생성                        │
│     → CREATE (ds:DataSource {name: 'erp_db', ...})       │
│  4. 연결 테스트 (SELECT 1)                                │
│  5. 성공 응답 반환                                        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 동기/비동기 경계

### 3.1 동기 작업 (즉시 응답)

| 작업 | 응답 시간 | 프로토콜 |
|------|----------|---------|
| 데이터소스 CRUD | < 1초 | REST JSON |
| 헬스체크 | < 2초 | REST JSON |
| MindsDB 상태 확인 | < 1초 | REST JSON |
| ML 모델/작업/KB 목록 | < 3초 | REST JSON |

### 3.2 비동기 작업 (스트리밍)

| 작업 | 소요 시간 | 프로토콜 |
|------|----------|---------|
| 메타데이터 추출 | 수초 ~ 수분 | SSE (Server-Sent Events) |
| SQL 쿼리 실행 | < 120초 (타임아웃) | REST JSON |
| 물리화 테이블 생성 | 수초 ~ 수분 | REST JSON |

### 3.3 SSE 스트리밍 구조

메타데이터 추출은 대량의 테이블/컬럼을 처리하므로 SSE로 진행률을 실시간 전송한다.

```
Client                              Weaver API
  │                                     │
  │  POST /datasources/{name}/          │
  │       extract-metadata              │
  │────────────────────────────────────▶│
  │                                     │
  │  event: progress                    │
  │  data: {"step": "schemas",          │
  │         "current": 1, "total": 3}   │
  │◀────────────────────────────────────│
  │                                     │
  │  event: progress                    │
  │  data: {"step": "tables",           │
  │         "schema": "public",         │
  │         "current": 5, "total": 20}  │
  │◀────────────────────────────────────│
  │                                     │
  │  event: progress                    │
  │  data: {"step": "columns",          │
  │         "table": "processes",       │
  │         "current": 12, "total": 15} │
  │◀────────────────────────────────────│
  │                                     │
  │  event: complete                    │
  │  data: {"total_schemas": 3,         │
  │         "total_tables": 20,         │
  │         "total_columns": 150}       │
  │◀────────────────────────────────────│
```

---

## 4. 실패 격리 지점

### 4.1 실패 시나리오와 영향 범위

| 실패 지점 | 영향 범위 | 격리 방법 |
|-----------|----------|----------|
| MindsDB 다운 | 쿼리 실행 불가 | 헬스체크 API로 사전 감지, 에러 응답 반환 |
| Neo4j 다운 | 메타데이터 저장/조회 불가 | 쿼리 실행은 정상 동작 (MindsDB 독립) |
| 대상 DB 다운 | 해당 DB 쿼리만 실패 | 다른 DB 쿼리는 정상, 헬스체크로 감지 |
| 네트워크 타임아웃 | 개별 요청 실패 | 120초 타임아웃, 재시도 없음 (멱등성 미보장) |

### 4.2 에러 전파 정책

```
금지사항:
  - MindsDB 에러를 그대로 클라이언트에 전달하지 않는다
  - 대상 DB의 내부 에러 메시지를 노출하지 않는다

필수사항:
  - 모든 에러는 Weaver 표준 에러 형식으로 변환한다
  - 연결 정보(호스트, 포트)는 에러 메시지에 포함하지 않는다
  - 타임아웃은 명시적으로 알린다
```

---

## 5. 외부 의존성

| 의존성 | 버전 | 필수 여부 | 대안 |
|--------|------|----------|------|
| MindsDB | 최신 | 필수 (쿼리 실행) | 없음 (핵심 게이트웨이) |
| Neo4j | 5.0+ | 필수 (메타데이터) | PostgreSQL JSONB (성능 트레이드오프) |
| asyncpg | 0.29+ | 선택 (PG 어댑터) | psycopg2 (동기) |
| aiomysql | 0.2+ | 선택 (MySQL 어댑터) | pymysql (동기) |
| httpx | 최신 | 필수 (HTTP 클라이언트) | aiohttp (대안) |
| Apache Airflow | 2.x | 선택 (ETL) | Prefect, Dagster (대안) |

---

## 6. 관련 문서

| 문서 | 설명 |
|------|------|
| `01_architecture/data-fabric.md` | 데이터 패브릭 설계 상세 |
| `01_architecture/adapter-pattern.md` | 어댑터 패턴 상세 |
| `03_backend/mindsdb-client.md` | MindsDB 클라이언트 구현 상세 |
| `99_decisions/ADR-001-mindsdb-gateway.md` | MindsDB 선택 근거 |
| `01_architecture/metadata-service.md` | 메타데이터 서비스 아키텍처 |
| `01_architecture/fabric-snapshot.md` | 패브릭 스냅샷 아키텍처 |
| `06_data/neo4j-schema-v2.md` | Neo4j 메타데이터 스키마 v2 (멀티테넌트) |
