# Oracle Full 스펙 구현 계획 (미구현·스텁·Mock 항목)

> **근거**: [docs/03_implementation/oracle/](.) (구현 계획), **코드 검증**: `services/oracle/app/`, `apps/canvas/src/features/nl2sql/` 실제 구현 대조  
> **범위**: 현재 스텁·Mock이거나 설계 문서(services/oracle/docs/) Full 스펙에 미달한 항목만. 설계 문서를 참조하여 단계별 구현 계획을 수립한다.  
> **작성일**: 2026-02-22

---

## 1. 목적

- Oracle의 **미구현**, **스텁**, **Mock 기반** 항목을 설계 문서(services/oracle/docs/)에 맞춰 Full 스펙으로 구현하기 위한 계획.
- Phase별 설계 문서 참조, 티켓, 선행 조건, 통과 기준을 명시. **갭은 코드 기준으로 검증한 결과를 반영.**

---

## 2. 참조 설계 문서

| 문서 | 용도 |
|------|------|
| **00_overview/system-overview.md** | Oracle 정체성, NL2SQL 8단계 파이프라인 요약, 기술 스택, K-AIR 이식 범위 |
| **01_architecture/architecture-overview.md** | 4계층(API·파이프라인·코어·데이터), 데이터 흐름, 외부 통합(Synapse·Target DB·OpenAI·Core) |
| **01_architecture/nl2sql-pipeline.md** | 5축 벡터 검색, 8단계 Ask 파이프라인, ReAct 6단계, 스키마 포맷팅·품질 게이트 |
| **01_architecture/sql-guard.md** | SQL Guard 검증 체계 |
| **01_architecture/cep-engine.md** | 이벤트/CEP (Core Watch 이관) |
| **02_api/text2sql-api.md** | /ask, /react, /direct-sql 요청/응답, 에러 코드, Rate limiting |
| **02_api/feedback-api.md** | POST /feedback, 쿼리 이력 |
| **02_api/meta-api.md** | 메타데이터 탐색 (테이블/컬럼/데이터소스) |
| **02_api/events-api.md** | 이벤트 룰 CRUD (Core Watch 프록시) |
| **03_backend/service-structure.md** | 서비스 내부 구조 |
| **05_llm/llm-factory.md**, **react-agent.md** | LLM 추상화, ReAct 에이전트 |
| **06_data/query-history.md** | 쿼리 이력 스키마·저장소 |
| **07_security/sql-safety.md**, **data-access.md** | SQL 안전성, 인증/테넌트 |
| **08_operations/deployment.md** | 배포·환경 |

---

## 3. 갭 요약 (코드 기준)

아래는 `services/oracle/app/` 및 Canvas NL2SQL 연동 코드를 확인한 결과이다. **미구현·스텁·Mock**만 기술한다.

| 영역 | 현재 상태 (코드) | Full 스펙 (설계 문서) |
|------|------------------|------------------------|
| **NL2SQL Ask 파이프라인** | **구현됨**: nl2sql_pipeline.execute에서 1.embed(llm_factory.embed) → 2.search_graph(question_vector)·_schema_from_search_result·fallback → 3._format_schema_ddl → 4._generate_sql_llm → 5.Guard → 6.execute_sql → 7.recommend_visualization → 8.summary(LLM)·cache_postprocessor. | nl2sql-pipeline.md: 1.임베딩 → 2.5축 벡터 검색 → 3.스키마 포맷팅 → 4.LLM SQL 생성 → 5.Guard → 6.실행 → 7.시각화 추천 → 8.캐싱(품질 게이트) |
| **ReAct 파이프라인** | **구현됨**: _select_tables(search_graph→list_schema_tables fallback), step select·generate·validate·fix·execute·quality·triage, sql_executor.execute_sql 호출, COMPLETE 시 step "result"(sql·result·summary·visualization), _error_step 형식. | nl2sql-pipeline.md, text2sql-api.md: Select(그래프 검색 기반), Generate·Validate·Fix·Execute·Quality·Triage, 최종 step "result" NDJSON |
| **인증** | **구현됨**: auth.py에서 jose JWT decode(JWT_SECRET_KEY·JWT_ALGORITHM). Core와 동일 기본 시크릿(axiom-dev-secret-key) 사용. 401/403 detail 형식 { code, message } 통일. | 07_security, architecture: JWT 검증, Core 인증 연동 |
| **Synapse 검색·캐시** | **구현됨**: `search_graph()` Synapse POST /api/v3/synapse/graph/search. `reflect_cache()`는 Synapse POST /api/v3/synapse/graph/query-cache 호출(question·sql·confidence·datasource_id). Synapse graph_search_service.add_query_cache 인메모리 반영. `list_datasources()`는 ORACLE_DATASOURCES_JSON 또는 하드코딩 목록. | nl2sql-pipeline: 5축 검색 결과 융합, 품질 게이트 통과 시 Query 노드 영속화(reflect_cache) |
| **SQL 실행** | `sql_exec.py`: Weaver 연동 경로 있음(`_execute_via_weaver`), **ORACLE_SQL_EXECUTION_MODE**에 따라 mock/weaver 분기. mock 시 결과 구조만 반환 | text2sql-api: Target DB(PostgreSQL/MySQL) 실행, 타임아웃 30초, 최대 10,000행 |
| **시각화 추천** | `nl2sql_pipeline.py`: **응답에 visualization 필드 없음**. metadata만 반환 | text2sql-api: data.visualization (chart_type, config), include_viz 옵션 |
| **요약(LLM)** | `nl2sql_pipeline.py`: **summary 필드 없음** | text2sql-api: data.summary (결과 요약) |
| **Rate limiting** | `text2sql.py`, `main.py`: **미들웨어 없음** | text2sql-api §5.3: /ask 30/분, /react 10/분, /direct-sql 60/분 |
| **이벤트 API** | `events.py`: Core Watch 프록시 구현됨. 설계 대로 이관 완료 | events-api: Implemented (Core Watch Proxy) |
| **피드백·메타·이력** | `feedback.py`, `meta.py`: 구현됨. `query_history_repo`: PostgreSQL 연동(스키마 oracle.query_history), fallback 인메모리 존재 | feedback-api, meta-api, query-history: 구현 상태 유지 |
| **Canvas 연동** | **구현됨**: `oracleNl2sqlApi.ts`에서 `oracleApi`(createApiClient) 사용. postAsk·getHistory는 oracleApi.post/get, postReactStream은 oracleApi.defaults.baseURL 기반 NDJSON 스트림. VITE_ORACLE_URL 기본 8004. | 동일 계약 유지, oracleApi 통일 완료 |

**이미 구현된 항목 (참고)**  
- SQL Guard: `sql_guard.py` — SQLGlot 파싱, 금지 키워드, SELECT만 허용, LIMIT 주입, join/subquery 깊이 제한.  
- text2sql 라우터: /ask, /react, /direct-sql, /history, /history/{id}. 역할 검사(admin/manager/attorney/analyst/engineer).  
- Events: Core Watch 프록시(규칙 CRUD, 스케줄러, stream, watch-agent/chat).  
- Feedback: query_history_repo.save_feedback.  
- Meta: Synapse list_schema_tables/get_schema_table + fallback, datasources, description 업데이트.  
- Query history: PostgreSQL oracle.query_history 테이블, save/list/get, fallback.

---

## 4. Phase 개요

| Phase | 목표 | 설계 문서 | 선행 | 상태 |
|-------|------|-----------|------|------|
| **O1** | NL2SQL Ask 파이프라인 Full (임베딩·5축 검색·LLM SQL·시각화·캐시) | nl2sql-pipeline.md, text2sql-api.md | Synapse Graph API 5축 검색·Neo4j 확정 | 완료 |
| **O2** | ReAct 파이프라인 Full (Select 그래프 기반·Execute·result 스트림) | nl2sql-pipeline.md, react-agent.md | O1 또는 Synapse search_graph 연동 | 완료 |
| **O3** | 인증 JWT/Core 연동 | 07_security, architecture | Core 인증 API 확정 | 완료 |
| **O4** | Synapse reflect_cache·품질 게이트 | nl2sql-pipeline.md §8, 06_data | Synapse Query 노드 영속 API 확정 | 완료 |
| **O5** | Rate limiting·문서 동기화 | text2sql-api.md §5.3 | - | 완료 |
| **O6** | (선택) Canvas oracleApi 통일·SSOT | service-endpoints-ssot.md | - | 완료 |

---

## 5. Phase O1: NL2SQL Ask 파이프라인 Full

**목표**: 8단계 파이프라인을 설계대로 구현. 임베딩 → 5축 그래프 검색 → 스키마 포맷팅 → LLM SQL 생성 → Guard → 실행 → 시각화 추천 → 캐시(품질 게이트).

### 5.1 참조 설계

- **nl2sql-pipeline.md** §1.1: 8단계 순서, 각 단계 입출력.
- **nl2sql-pipeline.md** §2: 5축 벡터 검색(question_vector, hyde_vector, regex, intent, PRF), Synapse Graph API.
- **architecture-overview.md** §3.1: 데이터 흐름(embed → graph_search → generate_sql → guard → execute → visualize).
- **text2sql-api.md**: data.visualization, data.summary, metadata 필드.

### 5.2 선행 조건

- Synapse Graph API에서 5축 검색(또는 통합 검색) 스펙 확정. OpenAI(또는 설정된 LLM) 임베딩·채팅 사용 가능.
- LLM Factory(`llm_factory`)에서 SQL 생성용 프롬프트·구조화 출력 사용 가능.

### 5.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| O1-1 | 임베딩 단계 | 질문 텍스트 → 벡터(OpenAI text-embedding-3-small 또는 설정). 파이프라인 진입점에 추가. | nl2sql_pipeline.py, embedding 호출 |
| O1-2 | 5축 그래프 검색 연동 | Synapse search_graph(또는 5축 검색 API) 호출, 결과 테이블/컬럼/유사 쿼리·값 매핑 반영. fallback은 기존 유지. | nl2sql_pipeline.py, synapse_client.search_graph 활용 |
| O1-3 | LLM SQL 생성 | 규칙 기반 _generate_sql 대신 LLM 기반 SQL 생성(스키마 DDL·질문·값 매핑·프롬프트). llm_factory·prompt 참조. | nl2sql_pipeline.py, 05_llm/prompt-engineering 반영 |
| O1-4 | 시각화 추천 | 결과 컬럼 타입·행 수 기반 chart_type/config 추천. options.include_viz false 시 null. | nl2sql_pipeline.py 또는 core/visualize, data.visualization |
| O1-5 | 결과 요약(LLM) | 실행 결과를 LLM으로 요약하여 data.summary 설정. (선택) | nl2sql_pipeline.py, data.summary |
| O1-6 | 캐시/품질 게이트(선택) | 신뢰도 ≥ 임계값 시 reflect_cache 호출. synapse_client.reflect_cache 실구현(Neo4j Query 노드). | synapse_client.reflect_cache, 백그라운드 태스크 |

### 5.4 통과 기준 (Gate O1)

- /ask 요청 시 임베딩·그래프 검색(또는 fallback)·LLM SQL 생성·Guard·실행이 순서대로 수행된다.
- 응답에 data.visualization(chart_type, config), data.summary(선택)가 포함된다.
- text2sql-api.md §2.3 응답 형식과 불일치 없음.

**구현 상태**: nl2sql_pipeline.execute에 O1-1~O1-5·캐시 후처리 반영. embed→search_and_catalog→_generate_sql_llm→guard→execute→recommend_visualization→summary·cache_postprocessor.

---

## 6. Phase O2: ReAct 파이프라인 Full

**목표**: ReAct 스트림이 Select(그래프 기반)·Execute(실제 SQL)·최종 step "result"를 포함하도록 구현.

### 6.1 참조 설계

- **nl2sql-pipeline.md** §1.2: ReAct 6단계(Select → Generate → Validate → Fix → Execute → Quality → Triage).
- **text2sql-api.md** §3.3: NDJSON step 유형(select, generate, validate, fix, execute, quality, triage, result, error).
- **react_agent.py**: 현재 Select 고정, Execute 미실행, COMPLETE 시 result 미전송.

### 6.2 선행 조건

- Synapse search_graph(또는 스키마 검색)로 테이블 후보 확보 가능.
- sql_executor.execute_sql를 ReAct 루프 내에서 호출 가능(동일 사용자·datasource).

### 6.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| O2-1 | Select 단계 그래프 기반 | session.question·datasource_id로 search_graph(또는 list_schema_tables) 호출, 테이블 후보를 step "select" data.tables로 전송. | react_agent.py |
| O2-2 | Execute 단계 실연동 | Validate 통과 SQL에 대해 sql_executor.execute_sql 호출, row_count·preview를 step "execute"로 전송. | react_agent.py |
| O2-3 | 최종 step "result" 전송 | triage.action == "COMPLETE" 시 step "result" 한 줄 전송: sql, result, summary, visualization. 이후 스트림 종료. | react_agent.py |
| O2-4 | step "error" 형식 통일 | 실패 시 text2sql-api §3.4 형식으로 step "error" 전송. | react_agent.py |

### 6.4 통과 기준 (Gate O2)

- /react 스트림에서 select 데이터가 그래프/스키마 기반 테이블 목록을 담는다.
- validate 통과 후 execute 단계에서 실제 실행 결과(preview)가 NDJSON으로 전달된다.
- COMPLETE 시 마지막에 step "result"가 오며, Canvas에서 최종 결과를 표시할 수 있다.

**구현 상태**: react_agent.stream_react_loop에서 _select_tables(search_graph→list_schema_tables), execute 단계 sql_executor.execute_sql, COMPLETE 시 step "result"(sql·result·summary·visualization), _error_step 형식.

---

## 7. Phase O3: 인증 JWT/Core 연동

**목표**: Mock 토큰 검증을 제거하고, Core 인증(JWT 검증 또는 토큰 전달 검증)과 연동한다.

### 7.1 참조 설계

- **07_security/data-access.md**: 인증·테넌트 격리.
- **architecture-overview.md**: Core 인증, JWT 검증.
- **auth.py**: 현재 verify_token이 문자열 역할만 판별.

### 7.2 선행 조건

- Core에서 JWT 발급·검증 방식 확정. Oracle이 Core에 검증 요청할지, 공개키로 직접 검증할지 결정.

### 7.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| O3-1 | JWT 검증 연동 | Core 검증 API 호출 또는 공개키로 JWT 검증, tenant_id·user_id·role·permissions 추출. | app/core/auth.py |
| O3-2 | Authorization 헤더 규약 | Bearer 토큰 필수, 401/403 응답 형식 통일. | auth.py, text2sql/feedback/meta/events 라우터 |

### 7.4 통과 기준 (Gate O3)

- Authorization: Bearer {Core JWT} 로 요청 시 사용자·테넌트가 올바르게 해석되고, 역할 기반 접근이 동작한다.
- Mock 토큰 문자열 역할 분기 제거.

**구현 상태**: O3-1 JWT_SECRET_KEY 기본값을 Core와 동일(axiom-dev-secret-key)로 통일, sub/tenant_id/role/permissions 추출. O3-2 401/403 detail을 { "code": "UNAUTHORIZED"|"FORBIDDEN", "message": "..." } 형식으로 통일.

---

## 8. Phase O4: Synapse reflect_cache·품질 게이트

**목표**: 품질 게이트 통과 시 생성 SQL·결과를 Synapse(Neo4j Query 노드)에 반영. reflect_cache 실구현.

### 8.1 참조 설계

- **nl2sql-pipeline.md** §8: 품질 게이트, 신뢰도 ≥ 0.90, Neo4j Query 노드 영속화.
- **synapse_client.py**: reflect_cache(question, sql, confidence, datasource_id) — Synapse POST /api/v3/synapse/graph/query-cache 실호출로 구현됨.

### 8.2 선행 조건

- Synapse API에 Query 노드 생성/갱신 엔드포인트(또는 graph 업데이트) 스펙 확정.

### 8.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| O4-1 | reflect_cache 실구현 | Synapse 호출(POST/PUT 등)로 question·sql·confidence·datasource_id 전달, Query 노드 영속. | synapse_client.reflect_cache |
| O4-2 | 품질 게이트 트리거 | Ask 파이프라인에서 신뢰도 점수 계산(LLM 또는 휴리스틱), 임계값 이상 시 reflect_cache 호출(백그라운드). | nl2sql_pipeline.py |

### 8.4 통과 기준 (Gate O4)

- 품질 게이트 조건 충족 시 reflect_cache가 호출되며, Synapse 측에 쿼리 정보가 반영된다.
- 스텁 `{"success": True}` 제거.

**구현 상태**: O4-1 Synapse에 POST /api/v3/synapse/graph/query-cache 추가, body(question, sql, confidence, datasource_id). graph_search_service.add_query_cache(인메모리 _similar_queries 추가/갱신). Oracle synapse_client.reflect_cache는 해당 URL로 POST 실호출, 스텁 제거. O4-2 품질 게이트 트리거는 nl2sql_pipeline/cache_postprocess에서 이미 호출 중.

---

## 9. Phase O5: Rate limiting·문서 동기화

**목표**: text2sql-api.md §5.3 Rate Limiting 적용, 문서 상태 태그 갱신.

### 9.1 참조 설계

- **02_api/text2sql-api.md** §5.3: /ask 30/분, /react 10/분, /direct-sql 60/분 (사용자별).
- **07_security**: 보안·제한 정책.

### 9.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| O5-1 | Rate limit 미들웨어 | slowapi 또는 동등, 사용자(또는 tenant+user)별 분당 제한, 429 응답. | app/core 또는 middleware |
| O5-2 | 문서 갱신 | text2sql-api.md "Partial (Mock-backed)" → 구현 상태 반영. 01_oracle-fullspec-implementation-plan.md Phase 완료 시 갱신. | text2sql-api.md |

### 9.3 통과 기준 (Gate O5)

- 제한 초과 시 429와 표준 에러 본문이 반환된다.
- 문서에 구현 상태가 반영된다.

**구현 상태**: O5-1 app/core/rate_limit.py InMemoryRateLimiter, 사용자별 key(text2sql:ask|react|direct_sql:{user_id}), /ask 30/분·/react 10/분·/direct-sql 60/분. RateLimitExceeded → exception handler에서 429 + Retry-After 헤더·error 본문 반환. O5-2 text2sql-api.md 구현 상태·Phase O5 완료 반영.

---

## 10. Phase O6: (선택) Canvas oracleApi 통일·SSOT

**목표**: Canvas에서 Oracle 호출을 createApiClient 기반 oracleApi로 통일, SSOT에 Oracle 포트/URL 반영.

### 10.1 참조 설계

- **apps/canvas/src/lib/api/clients.ts**: oracleApi = createApiClient(VITE_ORACLE_URL).
- **oracleNl2sqlApi.ts**: oracleApi(createApiClient) 사용. postAsk·getHistory는 oracleApi.post/get, postReactStream은 baseURL 기반 createNdjsonStream. JWT는 createApiClient 인터셉터로 주입.
- **docs/02_api/service-endpoints-ssot.md**: Oracle 포트·Base URL·Canvas VITE_ORACLE_URL 명시됨.

### 10.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| O6-1 | oracleNl2sqlApi에서 oracleApi 사용 | postAsk, getHistory 등에서 fetch 대신 oracleApi.get/post 호출, 응답 형식(createApiClient는 response.data 반환) 맞춤. | oracleNl2sqlApi.ts |
| O6-2 | SSOT 반영 | service-endpoints-ssot.md에 Oracle 서비스 포트·Base URL 추가(있는 경우). | service-endpoints-ssot.md |

### 10.3 통과 기준 (Gate O6)

- NL2SQL 기능이 oracleApi를 통해 호출되며, 인증·에러 처리 일관성 유지.
- SSOT에 Oracle 엔드포인트가 명시된다.

**구현 상태**: O6-1 oracleNl2sqlApi.ts는 이미 oracleApi 사용(postAsk oracleApi.post, getHistory oracleApi.get, postReactStream은 oracleApi.defaults.baseURL으로 스트림 URL 구성). O6-2 service-endpoints-ssot.md §1·§2에 Oracle 포트 8004·Base URL·VITE_ORACLE_URL 및 §2.1 실제 API 경로 반영됨.

---

## 11. 권장 실행 순서

1. **Phase O3 (인증)** — 다른 Phase에서 사용자/테넌트를 신뢰할 수 있도록 선행 권장.
2. **Phase O1 (Ask 파이프라인)** — 단일 질의 품질·응답 형식 완성.
3. **Phase O2 (ReAct)** — 다단계 추론·스트림 완성.
4. **Phase O4 (reflect_cache)** — Synapse 스펙 확정 후.
5. **Phase O5 (Rate limit·문서)** — 운영·문서 정리.
6. **Phase O6** — 프론트 정리 시.

---

## 12. 문서 갱신

- 각 Phase 완료 시 **02_api/text2sql-api.md** 상단 구현 상태 태그를 갱신한다.
- **future-implementation-backlog.md**에 Oracle 섹션이 있으면 코드 재검증 후 갱신한다.
- **docs/03_implementation/oracle/README.md**에 본 문서(01_oracle-fullspec-implementation-plan.md) 링크를 추가한다.
