# Weaver Full 스펙 구현 계획 (미구현·스텁·Mock 항목)

> **근거**: [docs/implementation-plans/weaver/](.) (구현 계획), **코드 검증**: `services/weaver/app/` 실제 구현 대조  
> **범위**: 현재 스텁·Mock이거나 설계 문서(services/weaver/docs/) Full 스펙에 미달한 항목만. 설계 문서를 참조하여 단계별 구현 계획을 수립한다.  
> **작성일**: 2026-02-23

---

## 1. 목적

- Weaver의 **미구현**, **스텁**, **Mock 기반** 항목을 설계 문서(services/weaver/docs/)에 맞춰 Full 스펙으로 구현하기 위한 계획.
- Phase별 설계 문서 참조, 티켓, 선행 조건, 통과 기준을 명시. **갭은 코드 기준으로 검증한 결과를 반영.**

---

## 2. 참조 설계 문서

| 문서 | 용도 |
|------|------|
| **00_overview/system-overview.md** | Weaver 정체성, 데이터 패브릭·메타데이터 추출·다중 DB·K-AIR 이식 현황 |
| **01_architecture/architecture-overview.md** | 전체 아키텍처, extract-metadata 경로 |
| **01_architecture/adapter-pattern.md** | PostgreSQLAdapter, MySQLAdapter, OracleAdapter, AdapterFactory |
| **01_architecture/metadata-service.md** | 메타데이터 서비스, extract-metadata 완료 시 스냅샷 연동 |
| **02_api/datasource-api.md** | 데이터소스 CRUD, 스키마/테이블/샘플 조회, **extract-metadata 미언급(metadata-api)** |
| **02_api/metadata-api.md** | **POST /api/datasources/{name}/extract-metadata** SSE 스트리밍, 지원 엔진, 이벤트 타입 |
| **02_api/metadata-catalog-api.md** | /api/v1/metadata 스냅샷·글ossary·태그·검색·통계 |
| **02_api/query-api.md** | POST /api/query, materialized-table, 타임아웃·보안·감사 |
| **03_backend/schema-introspection.md** | IntrospectionService.extract_metadata, AdapterFactory, SSE 이벤트 |
| **03_backend/mindsdb-client.md** | MindsDB API 호출 |
| **03_backend/neo4j-metadata.md** | Neo4j 메타데이터 저장 |
| **06_data/neo4j-schema.md**, **neo4j-schema-v2.md** | 그래프 스키마, 계보 필드 |
| **07_security/connection-security.md**, **data-access.md** | 연결 보안, 테넌트 격리 |
| **08_operations/deployment.md** | 배포·환경 |

---

## 3. 갭 요약 (코드 기준)

아래는 `services/weaver/app/` 및 설계 문서를 대조한 결과이다. **미구현·스텁·Mock**만 기술한다.

| 영역 | 현재 상태 (코드) | Full 스펙 (설계 문서) |
|------|------------------|------------------------|
| **메타데이터 추출 API** | **구현됨**: POST /api/datasources/{name}/extract-metadata. introspection_service.extract_metadata_stream → SSE( started/schema_found/table_found/columns_extracted/fk_extracted/complete ). 완료 시 weaver_runtime.datasources 카탈로그·metadata_extracted 갱신. | metadata-api.md: SSE 스트리밍, 어댑터 호출 → 카탈로그 저장 |
| **어댑터** | **구현됨**: get_adapter(engine, connection). PostgresAdapter(dsn), MySQLAdapter(connection·aiomysql), OracleAdapter(connection·stub). connection_to_pg_dsn, adapters.py. | adapter-pattern.md, metadata-api.md: PostgreSQL·MySQL·Oracle(스텁) |
| **데이터소스 카탈로그** | **인메모리/기본값**: datasource 생성 시 weaver_runtime.datasources에 저장. schemas/tables/schema/sample은 _default_catalog 또는 ds["catalog"] 반환. extract-metadata 미구현으로 실제 DB 스키마 갱신 경로 없음. | datasource-api.md: 스키마/테이블/컬럼/FK는 추출 결과 또는 Neo4j에서 조회 |
| **쿼리 실행** | **구현됨**: external_mode 시 MindsDB 실행. 미설정 시 Mock(문서화 유지). | query-api.md: MindsDB SQL 쿼리 실행, execution_time_ms·column_types |
| **물리화 테이블** | **구현됨**: external_mode에서 CREATE 후 COUNT(*)·SELECT * LIMIT 1로 row_count·columns 실제 반영. | query-api.md: row_count·columns·created_at 실제 값 |
| **Legacy POST /query** | **Mock**: execute_graph_query는 blocklist 체크 후 고정 records 반환. 실제 그래프/패브릭 쿼리 아님. | (레거시 계약 유지 또는 제거) |
| **인증** | **구현됨**: app/core/auth.py JWT decode, CurrentUser(sub, tenant_id, role, permissions), datasource:read/write, query:read/execute, metadata:read/write/admin. JWT_SECRET_KEY 기본 weaver-dev-secret-change-me. | 07_security, data-access: JWT·테넌트 격리. Core와 동일 시크릿 사용 시 연동 가능. |
| **MindsDB·Neo4j·PG** | **구현됨**: mindsdb_client(health, show_databases, create_database, drop_database, execute_query). neo4j_metadata_store·postgres_metadata_store(스냅샷·글ossary·태그). metadata_catalog API 전부 PG/Neo4j 또는 인메모리. | 설계 대로. |
| **Idempotency·Rate limit** | **구현됨**: request_guard.idempotency_store, rate_limiter. query·datasource·metadata write 경로 적용. | datasource-api.md, query-api.md: Idempotency-Key, Rate Limit 429 |

**이미 구현된 항목 (참고)**  
- 데이터소스 CRUD: MindsDB create_database/drop_database(external_mode), weaver_runtime, PG/Neo4j upsert_datasource/delete_datasource.  
- 메타데이터 카탈로그: 스냅샷 CRUD·diff·restore, 글ossary CRUD·search, 테이블/컬럼 태그, /search, /stats.  
- SchemaIntrospector: introspect(extracted_schema) → GraphSchema (app/core/schema_introspection.py).  
- 감사 로그·메트릭·Circuit Breaker(resilience)·에러 코드 표준화.

---

## 4. Phase 개요

| Phase | 목표 | 설계 문서 | 선행 | 상태 |
|-------|------|-----------|------|------|
| **W1** | 메타데이터 추출 API (extract-metadata SSE) | metadata-api.md, schema-introspection.md | 어댑터(Postgres 사용 가능) | 완료 |
| **W2** | MySQL·Oracle 어댑터 | adapter-pattern.md, metadata-api.md | W1 또는 독립 | 완료 |
| **W3** | 쿼리·물리화 Mock 제거/보완 | query-api.md | MindsDB 안정 | 완료 |
| **W4** | (선택) JWT Core 연동·문서 | 07_security, data-access | Core 인증 API 확정 | 완료 |
| **W5** | (선택) 문서 동기화 | 02_api, 98_gate-pass-criteria | - | 완료 |
| **W6** | 갭: 추출 결과 Neo4j 저장 | metadata-api §2.1, neo4j-schema.md | W1 | 완료 |
| **W7** | 갭: SSE progress/error·옵션 반영 | metadata-api §2.4 | W1 | 완료 |
| **W8** | 갭: FK 추출 | metadata-api §2.4, adapters | W1 | 완료 |
| **W9** | 갭: OracleAdapter 실구현 (선택) | metadata-api §2.2 | W2 | 완료 |

---

## 5. Phase W1: 메타데이터 추출 API (extract-metadata SSE)

**목표**: `POST /api/datasources/{name}/extract-metadata` 구현. SSE 스트리밍으로 진행 이벤트 전송, 어댑터 호출 → 스키마 추출 → Neo4j(또는 weaver 런타임) 저장.

### 5.1 참조 설계

- **02_api/metadata-api.md**: POST /api/datasources/{name}/extract-metadata, Accept: text/event-stream. body: schemas, include_sample_data, sample_limit, include_row_counts. 이벤트: started, schema_found, table_found, columns_extracted, fk_extracted, complete.
- **03_backend/schema-introspection.md**: IntrospectionService.extract_metadata(datasource_name, engine, connection_params, target_schemas, ...), AdapterFactory.get_adapter(engine, connection_params), adapter.get_schemas() → get_tables() → get_columns()/get_foreign_keys(), metadata_store 저장.
- **app/core/adapters.py**: DataSourceAdapter(test_connection, extract_schema). PostgresAdapter(실제 구현됨). connection에서 DSN 또는 host/port/database/user/password 조합으로 어댑터 생성 필요.

### 5.2 선행 조건

- 데이터소스가 이미 등록되어 있으며 connection 정보를 조회할 수 있음.
- 지원 엔진(postgresql 등)에 대해 어댑터가 존재함(현재 PostgresAdapter만 구현).

### 5.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| W1-1 | extract-metadata 엔드포인트 | POST /api/datasources/{name}/extract-metadata, StreamingResponse(text/event-stream). 권한 datasource:write 또는 metadata:write. | app/api/datasource.py 또는 별도 라우터 |
| W1-2 | IntrospectionService 또는 동등 오케스트레이션 | datasource 조회 → engine/connection으로 어댑터 생성 → extract_schema 호출 → 이벤트 생성(yield). schema_introspection.SchemaIntrospector.introspect 활용. | app/services/introspection_service.py 또는 app/api 내 인라인 |
| W1-3 | SSE 이벤트 포맷 | started, schema_found, table_found, columns_extracted, fk_extracted, complete. metadata-api.md §2.4 준수. | 이벤트 페이로드 구조 |
| W1-4 | 추출 결과 저장 | Neo4j(metadata_external_mode) 또는 weaver_runtime.datasources[ds_key]["catalog"] 갱신. metadata_extracted=True, tables_count/schemas_count 설정. | neo4j_metadata_store 또는 weaver_runtime |

### 5.4 통과 기준 (Gate W1)

- POST /api/datasources/{name}/extract-metadata 호출 시 200 + text/event-stream 응답이 반환되고, started → (schema/table/columns/fk) → complete 순서로 이벤트가 수신된다.
- 지원 엔진(postgresql)으로 등록된 데이터소스에 대해 실제 DB에서 스키마가 추출되어 Neo4j 또는 런타임 카탈로그에 반영된다.
- 설계 문서(metadata-api.md)의 이벤트 타입·필드와 불일치 0건.

**구현 상태**: W1-1 POST /api/datasources/{name}/extract-metadata 추가(StreamingResponse). W1-2 extract_metadata_stream(introspection_service), get_adapter → extract_schema → SSE 이벤트 yield. W1-3 started/schema_found/table_found/columns_extracted/fk_extracted/complete. W1-4 complete 시 weaver_runtime.datasources[ds_key] catalog·metadata_extracted·tables_count·schemas_count 갱신.

---

## 6. Phase W2: MySQL·Oracle 어댑터

**목표**: adapter-pattern.md·metadata-api.md에 따른 MySQLAdapter, OracleAdapter 구현. extract-metadata에서 엔진별 어댑터 사용.

### 6.1 참조 설계

- **01_architecture/adapter-pattern.md**: MySQLAdapter, OracleAdapter 시그니처(BaseAdapter 상속, connect, get_schemas, get_tables, get_columns, get_foreign_keys 등). 설계서 내 코드 예시 참고.
- **02_api/metadata-api.md**: 지원 엔진 PostgreSQL, MySQL, Oracle. GET /api/datasources/supported-engines에 oracle 포함(현재 _SUPPORTED_ENGINES에 이미 "oracle" 포함).
- **app/core/adapters.py**: DataSourceAdapter(ABC), test_connection, extract_schema. PostgresAdapter는 DSN 또는 connection dict로 생성 가능하도록 확장 가능.

### 6.2 선행 조건

- W1에서 어댑터를 AdapterFactory 또는 engine별 분기로 생성하는 구조가 있음.
- (선택) aiomysql·cx_Oracle 또는 oracledb 등 비동기/동기 드라이버 의존성 결정.

### 6.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| W2-1 | MySQLAdapter | connection(host, port, database, user, password)로 연결, information_schema 기반 스키마/테이블/컬럼/FK 추출. test_connection, extract_schema. | app/core/adapters.py 또는 adapters/mysql.py |
| W2-2 | OracleAdapter | connection으로 Oracle DB 연결, ALL_TAB_COLUMNS 등 뷰 기반 추출. test_connection, extract_schema. | app/core/adapters.py 또는 adapters/oracle.py |
| W2-3 | AdapterFactory 또는 engine별 분기 | engine 문자열로 PostgresAdapter/MySQLAdapter/OracleAdapter 반환. extract-metadata에서 사용. | app/core/adapters.py 또는 app/services/introspection_service.py |

### 6.4 통과 기준 (Gate W2)

- engine=mysql, oracle인 데이터소스에 대해 extract-metadata 호출 시 해당 어댑터가 사용되어 스키마가 추출된다.
- test_connection(또는 POST .../test)이 해당 엔진에서 성공/실패를 반환한다.

**구현 상태**: W2-1 MySQLAdapter(connection, aiomysql), extract_schema·test_connection. W2-2 OracleAdapter(connection), extract_schema NotImplementedError(stub), oracledb optional. W2-3 get_adapter(engine, connection)으로 Postgres/MySQL/Oracle 반환.

---

## 7. Phase W3: 쿼리·물리화 Mock 제거/보완

**목표**: query-api.md 계약 충족. external_mode 미설정 시 동작 정책 확정(Mock 유지 시 문서화, 제거 시 MindsDB 필수).

### 7.1 참조 설계

- **02_api/query-api.md**: POST /api/query 응답에 execution_time_ms, column_types, 실제 row_count. POST /api/query/materialized-table 응답에 row_count, columns 실제 값.
- **app/api/query.py**: external_mode False 시 mock_rows = _mock_limit(sql), rows = [[f"value-{i}", i] for i in range(mock_rows)]. materialized-table 시 row_count = 25 하드코딩.

### 7.2 선행 조건

- MindsDB 연동이 운영 환경에서 사용될 경우 external_mode=true 권장. Mock 모드는 로컬/테스트 전용으로 문서 명시 가능.

### 7.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| W3-1 | materialized-table row_count·columns 실제 반영 | external_mode에서 CREATE TABLE 실행 후 SELECT COUNT(*), 정보 스키마 조회로 row_count·columns 채우기. | query.py create_materialized_table |
| W3-2 | POST /api/query Mock 정책 | Mock 유지 시 query-api.md에 "external_mode=false 시 Mock 응답" 명시. 제거 시 WEAVER_EXTERNAL_MODE 필수 안내. | query-api.md 또는 config 문서 |
| W3-3 | execution_time_ms | 이미 started/elapsed_ms 계산함. external_mode 경로에서도 동일 적용 확인. | query.py (검증) |

### 7.4 통과 기준 (Gate W3)

- materialized-table 생성 응답에 실제 row_count(또는 0)와 columns가 반환된다.
- 문서와 런타임 동작 불일치 0건.

**구현 상태**: W3-1 external_mode에서 CREATE TABLE 후 COUNT(*)·SELECT * LIMIT 1로 row_count·columns 채움. W3-2 Mock 정책은 문서 유지.

---

## 8. Phase W4: (선택) JWT Core 연동·문서

**목표**: Core가 발급한 JWT를 Weaver에서 검증할 수 있도록 JWT_SECRET_KEY(및 issuer/audience) 정책 정리. 401/403 응답 형식 통일.

### 8.1 참조 설계

- **07_security/data-access.md**: 인증·테넌트 격리.
- **Core**: 동일 JWT 시크릿 사용 시 Core 발급 토큰으로 Weaver API 호출 가능.

### 8.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| W4-1 | JWT_SECRET_KEY 기본값 정책 | Core와 동일 개발용 기본값 사용 여부 결정. config.py 또는 env 예시. | app/core/config.py, 문서 |
| W4-2 | 401/403 detail 형식 | { "code": "UNAUTHORIZED"|"FORBIDDEN", "message": "..." } 통일. | app/core/auth.py |

### 8.3 통과 기준 (Gate W4)

- 결정된 정책에 따라 JWT 검증 및 에러 응답이 일관된다.

---

## 9. Phase W5: (선택) 문서 동기화

**목표**: 02_api 문서의 구현 상태 태그(Implemented/Experimental/Planned)와 실제 코드 상태 동기화. 98_gate-pass-criteria 갱신.

### 9.1 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| W5-1 | metadata-api.md 상태 태그 | extract-metadata 구현 후 "Implemented" 또는 단계별 "Partial" 반영. | metadata-api.md |
| W5-2 | Gate W0~W3 체크리스트 | 98_gate-pass-criteria.md에 W1~W3 통과 항목 반영. | 98_gate-pass-criteria.md |
| W5-3 | future-implementation-backlog | Weaver 섹션 추가 시 코드 재검증 후 갱신. | future-implementation-backlog.md |

### 9.2 통과 기준 (Gate W5)

- API 문서 상태 태그와 런타임 구현 상태 불일치 0건.

---

## 10. 권장 실행 순서

1. **Phase W1 (extract-metadata)** — 메타데이터 추출 경로가 있으면 데이터소스 스키마/테이블/컬럼이 실제 DB 기준으로 갱신됨.
2. **Phase W2 (MySQL·Oracle 어댑터)** — 다중 엔진 지원 시 W1과 병행 또는 직후.
3. **Phase W3 (쿼리·물리화 보완)** — 운영 품질 개선.
4. **Phase W4, W5** — 정책·문서 정리.
5. **갭 보완** — §12 단계별 순서 권장.

---

## 11. 문서 갱신

- 각 Phase 완료 시 **02_api/metadata-api.md**, **02_api/query-api.md** 상단 구현 상태 태그를 갱신한다.
- **98_gate-pass-criteria.md**에 W1~W5 통과 항목을 반영한다.
- **future-implementation-backlog.md**에 Weaver 섹션이 있으면 코드 재검증 후 갱신한다.
- **99_traceability-matrix.md**는 기존 대로 유지하며, 본 문서(01_weaver-fullspec-implementation-plan.md) 링크를 README에 추가한다.

---

## 12. 갭 보완 단계별 구현 방안 (부분 구현 → 풀스펙)

현재 **부분 구현** 또는 **설계 대비 갭**이 있는 항목을 단계별로 풀스펙에 맞추기 위한 구현 방안이다. 선행 관계를 고려한 순서로 정리한다.

### 12.1 갭 목록 및 Phase 매핑

| Phase | 목표 | §참조 |
|-------|------|--------|
| W6 | 추출 결과 Neo4j 저장 (DataSource–Schema–Table–Column) | 12.3 |
| W7 | SSE progress·error 이벤트, include_sample_data·include_row_counts 반영 | 12.4 |
| W8 | Postgres/MySQL FK 추출, fk_extracted 페이로드·Neo4j FK 엣지 | 12.5 |
| W9 | OracleAdapter 실구현 (선택) | 12.6 |
| W4·W5 | JWT Core 연동·문서 동기화 (기존) | 12.7, §8·§9 |

### 12.2 갭 목록 요약

| 갭 | 현재 | 풀스펙(설계) | 우선순위 |
|----|------|--------------|----------|
| 추출 결과 Neo4j 저장 | weaver_runtime만 갱신 | metadata-api §2.1: Neo4j 그래프에 저장 | 높음 |
| SSE 이벤트 progress / neo4j_saved / error | 미발생 | metadata-api §2.4: progress, neo4j_saved, error | 중간 |
| include_sample_data / include_row_counts | 요청만 수신, 미사용 | metadata-api §2.3·§2.4: 샘플·행 수 반영 | 중간 |
| FK 추출 | fk_extracted 빈 데이터 | metadata-api §2.4: fk_count, targets | 중간 |
| OracleAdapter | 스텁(NotImplementedError) | metadata-api §2.2: Oracle 지원 | 낮음(선택) |
| JWT Core 연동·문서 | W4·W5 미완료 | 07_security, 문서 동기화 | 낮음 |

---

### 12.3 Phase W6: 추출 결과 Neo4j 저장

**목표**: extract-metadata 완료 시 추출된 카탈로그를 Neo4j에 DataSource–Schema–Table–Column(·FK) 구조로 저장. metadata_external_mode일 때만 수행.

**선행**: W1 완료(extract-metadata 엔드포인트·weaver_runtime 갱신 존재).

**참조**: 06_data/neo4j-schema.md (DataSource, Schema, Table, Column, :HAS_SCHEMA, :HAS_TABLE, :HAS_COLUMN, :FK_TO).

| 단계 | 제목 | 설명 | 산출 |
|------|------|------|------|
| W6-1 | Neo4j 메타데이터 쓰기 API | neo4j_metadata_store에 `save_extracted_catalog(tenant_id, datasource_name, catalog)` 추가. 기존 DataSource 노드 MERGE 후, 해당 datasource 하위 Schema/Table/Column 노드 생성·관계. (기존 스냅샷 노드와 별도) | neo4j_metadata_store.py |
| W6-2 | extract-metadata 완료 시 Neo4j 호출 | complete 이벤트 직전(또는 직후)에 settings.metadata_external_mode이면 neo4j_metadata_store.save_extracted_catalog 호출. 실패 시 error 이벤트 yield 후 재raise. | introspection_service.py 또는 datasource.py |
| W6-3 | neo4j_saved 이벤트 | Neo4j 저장 성공 시 `event: neo4j_saved`, data: nodes_created, relationships_created, duration_ms. | extract_metadata_stream |

**통과 기준**: metadata_external_mode=true, extract-metadata 호출 후 Neo4j에서 해당 datasource 하위 Schema/Table/Column 노드 조회 가능. neo4j_saved 이벤트 수신 가능.

**구현 상태**: W6-1 neo4j_metadata_store.save_extracted_catalog(tenant_id, datasource_name, catalog, engine) 추가. 기존 Schema 하위 그래프 삭제 후 DataSource MERGE, Schema(tenant_id, datasource_name, name)–Table–Column 생성, HAS_SCHEMA/HAS_TABLE/HAS_COLUMN 관계. 반환값 nodes_created, relationships_created, duration_ms. W6-2 extract-metadata 라우트 generate()에서 complete·_catalog 수신 시 metadata_external_mode이면 save_extracted_catalog 호출. W6-3 성공 시 neo4j_saved 이벤트, 실패 시 error 이벤트 후 NEO4J_UNAVAILABLE 예외.

---

### 12.4 Phase W7: SSE progress·error 이벤트 및 요청 옵션 반영

**목표**: metadata-api.md §2.4의 progress·error 이벤트 발생. include_sample_data·include_row_counts 옵션을 추출 단계에 반영.

**선행**: W1 완료. (W6 없이 진행 가능)

| 단계 | 제목 | 설명 | 산출 |
|------|------|------|------|
| W7-1 | progress 이벤트 | 스키마/테이블 단위 진행 시 progress 이벤트 yield. data: phase, completed, total, percent(, current_schema, current_table). | introspection_service.py |
| W7-2 | error 이벤트 | 어댑터/저장 예외 시 error 이벤트 yield 후 예외 전파. data: message, code(선택). | introspection_service.py, extract-metadata 라우트 |
| W7-3 | include_row_counts | 어댑터에서 테이블별 행 수 조회(예: PostgresAdapter에서 SELECT count(*) per table). table_found data에 row_count 포함. include_row_counts=false면 생략. | adapters.py, introspection_service.py |
| W7-4 | include_sample_data | 옵션 true일 때 테이블별 sample_limit행 조회, columns_extracted 또는 별도 sample_data 이벤트에 포함. 부하 고려해 선택 구현. | adapters.py 또는 introspection_service.py |

**통과 기준**: 진행 중 progress 이벤트 수신. 실패 시 error 이벤트 수신. include_row_counts true 시 table_found에 row_count 존재. include_sample_data는 부하 정책에 따라 생략 가능.

---

### 12.5 Phase W8: FK 추출

**목표**: PostgresAdapter·MySQLAdapter에서 FK 정보 추출. fk_extracted 이벤트에 fk_count, targets 등 채움.

**선행**: W1 완료. (W7과 병행 가능)

**참조**: metadata-api §2.4 fk_extracted 예시; 06_data/neo4j-schema.md :FK_TO.

| 단계 | 제목 | 설명 | 산출 |
|------|------|------|------|
| W8-1 | PostgresAdapter FK | information_schema.table_constraints + key_column_usage로 FK 조회. extract_schema 반환에 foreign_keys: [{source_table, source_column, target_schema, target_table, target_column}] 추가. | adapters.py PostgresAdapter |
| W8-2 | MySQLAdapter FK | information_schema.KEY_COLUMN_USAGE 등으로 FK 조회. 동일 구조로 반환. | adapters.py MySQLAdapter |
| W8-3 | 스트림 fk_extracted | extract_metadata_stream에서 테이블별 FK 있을 때 fk_extracted yield. data: schema, table, fk_count, targets. | introspection_service.py |
| W8-4 | Neo4j FK 관계 | W6 구현 시 save_extracted_catalog에서 :FK_TO 관계 생성. | neo4j_metadata_store (W6 연동) |

**통과 기준**: postgresql/mysql 데이터소스 extract-metadata 시 fk_extracted에 fk_count·targets 등 비어 있지 않음. (Neo4j 사용 시 FK 엣지 존재)

---

### 12.6 Phase W9: OracleAdapter 실구현 (선택)

**목표**: Oracle DB에 대한 메타데이터 추출. oracledb 패키지 기반.

**선행**: W2 완료(OracleAdapter 스텁 존재). oracledb 의존성 추가.

| 단계 | 제목 | 설명 | 산출 |
|------|------|------|------|
| W9-1 | oracledb 의존성 | requirements.txt에 oracledb 추가. | requirements.txt |
| W9-2 | OracleAdapter.extract_schema | connection(host, port, service_name/sid, user, password)로 연결. ALL_TAB_COLUMNS, ALL_CONSTRAINTS 등으로 스키마/테이블/컬럼/FK 추출. | adapters.py OracleAdapter |
| W9-3 | OracleAdapter.test_connection | oracledb.connect + ping 또는 SELECT 1 FROM DUAL. | adapters.py |

**통과 기준**: engine=oracle 데이터소스에 대해 extract-metadata 호출 시 스키마가 추출되고 카탈로그에 반영됨.

---

### 12.7 Phase W4·W5 (기존 선택 Phase)

- **W4**: JWT Core 연동(JWT_SECRET_KEY 기본값·401/403 본문 형식). §8 참조.
- **W5**: metadata-api.md 등 구현 상태 태그·98_gate-pass-criteria·future-implementation-backlog 갱신. §9 참조.

---

### 12.8 갭 보완 권장 순서

1. **W6 (Neo4j 저장)** — 설계상 “Neo4j 그래프에 저장” 충족.
2. **W7 (progress/error·옵션)** — SSE 계약 및 요청 옵션 풀스펙.
3. **W8 (FK 추출)** — fk_extracted 의미 부여, 그래프 품질 향상.
4. **W9 (Oracle)** — 엔진 확장 필요 시.
5. **W4·W5** — 정책·문서 정리.

의존성: W6-2에서 W8-4는 W6 완료 후 적용. W7·W8은 서로 독립적으로 병행 가능.
