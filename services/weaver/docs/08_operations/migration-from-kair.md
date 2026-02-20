# K-AIR fabric → Weaver 이식 가이드

<!-- affects: all modules -->
<!-- requires-update: none (standalone guide) -->

## 이 문서가 답하는 질문

- K-AIR의 어떤 코드를 Weaver로 이식하는가?
- 파일별 이식 매핑은?
- 이식 시 무엇을 변경하는가?
- 프론트엔드는 어떻게 처리하는가?
- 이식 순서와 예상 일정은?

---

## 1. 이식 범위

### 1.1 이식 대상 (robo-data-fabric-main)

| K-AIR 파일 | Weaver 파일 | 상태 |
|-----------|------------|------|
| `backend/app/routers/datasources.py` | `app/api/datasources.py` | 이식 (리팩토링) |
| `backend/app/routers/query.py` (69줄) | `app/api/query.py` | 이식 (리팩토링) |
| `backend/app/services/mindsdb_service.py` (308줄) | `app/mindsdb/client.py` | 이식 (리팩토링) |
| `backend/app/services/neo4j_service.py` (297줄) | `app/neo4j/metadata_store.py` | 이식 (리팩토링) |
| `backend/app/services/schema_introspection.py` (880줄) | `app/adapters/*.py` | 분할 이식 |
| `backend/app/schemas/datasource.py` | `app/schemas/datasource.py` | 이식 (Pydantic v2) |
| `backend/app/schemas/query.py` | `app/schemas/query.py` | 이식 (Pydantic v2) |

### 1.2 이식 제외

| K-AIR 파일 | 사유 |
|-----------|------|
| `frontend/` (Vue 3 전체) | Canvas(React 18)에서 재작성 |
| `backend/app/main.py` | Axiom 표준 구조로 재작성 |
| `requirements.txt` | `pyproject.toml`로 전환 |
| `.env` 파일 | Axiom 표준 환경 설정 |

---

## 2. 파일별 이식 상세

### 2.1 schema_introspection.py (880줄) → adapters/

가장 큰 파일이므로 분할 이식한다.

```
K-AIR: schema_introspection.py (880줄, 단일 파일)
│
├── class PostgreSQLAdapter → adapters/postgresql.py (분리)
├── class MySQLAdapter       → adapters/mysql.py (분리)
├── class BaseAdapter        → adapters/base.py (분리)
├── class AdapterFactory     → adapters/factory.py (분리)
└── (Oracle)                 → adapters/oracle.py (신규 추가)
```

**변경 사항**:
- 동기 드라이버(psycopg2, pymysql) → 비동기(asyncpg, aiomysql)
- 단일 파일 → 파일별 분리
- Oracle 어댑터 신규 추가
- 타입 힌트 강화

### 2.2 mindsdb_service.py (308줄) → mindsdb/client.py

```
K-AIR: mindsdb_service.py
│
├── execute_query()       → query() (이름 변경)
├── check_connection()    → health_check() (이름 변경)
├── get_databases()       → list_databases()
├── get_tables()          → list_tables()
├── get_table_schema()    → get_table_schema()
├── create_database()     → create_database()
└── drop_database()       → drop_database()
```

**변경 사항**:
- `httpx.Client` → `httpx.AsyncClient` (비동기)
- 프로덕션 인증 지원 추가
- 표준 에러 처리 (WeaverError 계층)
- 커넥션 풀 재사용

### 2.3 neo4j_service.py (297줄) → neo4j/metadata_store.py

```
K-AIR: neo4j_service.py
│
├── create_datasource_node()  → save_datasource()
├── create_schema_node()      → _create_schema_node() (내부)
├── create_table_node()       → _create_table_node() (내부)
├── create_column_node()      → _batch_create_columns() (배치화)
├── create_fk_relationship()  → _create_fk_relationship()
└── delete_datasource()       → delete_datasource_completely()
```

**변경 사항**:
- 개별 노드 생성 → 배치 UNWIND 생성 (성능)
- **password 속성 제거** (보안)
- 조회 쿼리 추가 (find_join_path 등)
- description 업데이트 메서드 추가 (LLM 보강용)

### 2.4 datasources.py (라우터) → api/datasources.py

**변경 사항**:
- Service 계층 분리 (라우터에서 비즈니스 로직 제거)
- Pydantic v2 모델 사용
- 표준 에러 응답 형식
- CORS 설정 강화

### 2.5 query.py (69줄) → api/query.py

**변경 사항**:
- DDL 쿼리 차단 로직 추가
- 감사 로깅 추가
- 기본 LIMIT 추가 (1000행)
- 물리화 테이블 API 추가

---

## 3. 이식 순서

```
Day 1: 기반 설정
├── pyproject.toml 작성 (의존성)
├── app/main.py (FastAPI 앱 초기화)
├── app/config.py (환경 설정)
├── app/core/errors.py (표준 에러)
└── docker-compose.dev.yml (개발 환경)

Day 2: MindsDB + Neo4j 클라이언트
├── app/mindsdb/client.py (← mindsdb_service.py)
├── app/neo4j/client.py (드라이버 래퍼)
├── app/neo4j/metadata_store.py (← neo4j_service.py)
└── 연결 테스트

Day 3: 어댑터 + API
├── app/adapters/base.py (BaseAdapter)
├── app/adapters/postgresql.py (← schema_introspection.py)
├── app/adapters/mysql.py (← schema_introspection.py)
├── app/adapters/oracle.py (신규)
├── app/adapters/factory.py
├── app/api/datasources.py (← routers/datasources.py)
├── app/api/query.py (← routers/query.py)
├── app/api/metadata.py (SSE 스트리밍)
├── app/schemas/*.py (← schemas/*.py, Pydantic v2)
└── 통합 테스트
```

**예상 총 일정**: 3일 (숙련 개발자 기준)

---

## 4. 의존성 전환

### 4.1 K-AIR → Weaver 의존성 매핑

| K-AIR | Weaver | 변경 이유 |
|-------|--------|----------|
| `fastapi==0.109` | `fastapi>=0.115` | 최신 버전 |
| `uvicorn` | `uvicorn[standard]` | HTTP/2 지원 |
| `httpx` | `httpx` | 동일 |
| `neo4j>=5.0` | `neo4j>=5.0` | 동일 |
| `asyncpg` | `asyncpg>=0.29` | 동일 |
| `aiomysql` | `aiomysql>=0.2` | 동일 |
| `pymysql` | (제거) | aiomysql로 대체 |
| `pydantic>=2.5` | `pydantic>=2.5` | 동일 |
| (없음) | `oracledb>=2.0` | Oracle 어댑터 추가 |
| (없음) | `pydantic-settings>=2.0` | 환경 설정 관리 |

### 4.2 pyproject.toml

```toml
[project]
name = "axiom-weaver"
version = "0.1.0"
description = "Axiom Data Fabric Service"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pydantic>=2.5",
    "pydantic-settings>=2.0",
    "neo4j>=5.0",
]

[project.optional-dependencies]
postgresql = ["asyncpg>=0.29"]
mysql = ["aiomysql>=0.2"]
oracle = ["oracledb>=2.0"]
all = ["asyncpg>=0.29", "aiomysql>=0.2", "oracledb>=2.0"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "httpx>=0.27"]
```

---

## 5. 검증 체크리스트

이식 완료 후 다음을 검증한다.

| 항목 | 검증 방법 |
|------|----------|
| MindsDB 연결 | `GET /api/query/status` → 200 OK |
| Neo4j 연결 | `GET /health/ready` → neo4j: ok |
| 데이터소스 생성 | `POST /api/datasources` → 201 Created |
| 데이터소스 목록 | `GET /api/datasources` → 목록 반환 |
| 메타데이터 추출 | `POST /extract-metadata` → SSE 이벤트 스트림 |
| 쿼리 실행 | `POST /api/query` → 결과 반환 |
| 데이터소스 삭제 | `DELETE /api/datasources/{name}` → 200 OK |
| 비밀번호 미노출 | GET 응답에 password 미포함 |
| Neo4j에 password 미저장 | Cypher 조회로 확인 |

---

## 6. 알려진 차이점

| 항목 | K-AIR | Weaver | 이유 |
|------|-------|--------|------|
| 프론트엔드 | Vue 3 내장 | 없음 (Canvas 별도) | 모듈 분리 |
| Pydantic | v1 스타일 | v2 (model_validator) | 표준 업그레이드 |
| Neo4j 비밀번호 | 평문 저장 | 미저장 | 보안 |
| CORS | `["*"]` | 특정 도메인 | 보안 |
| Oracle 지원 | 없음 | 있음 | 도메인 요구 |
| 에러 형식 | 비표준 | WeaverError 표준 | 일관성 |
| 테스트 | 없음 | pytest 필수 | 품질 |

---

## 7. 관련 문서

| 문서 | 설명 |
|------|------|
| `00_overview/system-overview.md` | Weaver 개요 |
| `03_backend/service-structure.md` | 서비스 구조 |
| `08_operations/deployment.md` | 배포 절차 |
