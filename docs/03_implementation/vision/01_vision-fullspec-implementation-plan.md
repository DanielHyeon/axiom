# Vision Full 스펙 구현 계획 (미구현·스텁·갭 항목)

> **근거**: [docs/05_backlog/future-backlog.md](../../future-implementation-backlog.md) §3, [docs/03_implementation/vision/](.) (00~99 구현 계획), services/vision/docs 및 **코드 검증 결과**  
> **범위**: 현재 스텁·인메모리·Mock이거나 설계 문서에 미달한 항목만. 설계 문서를 참조하여 단계별 구현 계획을 수립한다.  
> **작성일**: 2026-02-23  
> **구현 상태 (코드 기준 2026-02 검증)**: What-if CRUD·compute·compare·sensitivity·breakeven·process-simulation 라우트 존재(compute는 **공식 산식 스텁**, scipy 미사용; process-simulation 요청 스키마 설계와 상이). OLAP 라우트 전부 존재(**Mock 데이터·가짜 SQL**, Mondrian 파서·실제 MV 쿼리 미연동). Root Cause API·엔진·메트릭 **구현됨**. Analytics API는 **POST /execute·/what-if 스텁만** 존재(설계된 GET /summary·/cases/trend 등 6개 엔드포인트 미구현). ETL·NL→피벗·ScenarioSolver **Mock**. 상태 저장은 VisionStateStore(PostgreSQL 또는 SQLite fallback)로 영속.

---

## 1. 목적

- Vision의 **미구현**, **스텁**, **Mock** 또는 **설계 문서 대비 갭**인 항목을 services/vision/docs 및 docs/03_implementation/vision에 맞춰 Full 스펙으로 구현하기 위한 계획.
- Phase별 설계 문서 참조, 티켓, 선행 조건, 통과 기준을 명시.

---

## 2. 참조 설계 문서

| 문서 | 용도 |
|------|------|
| **00_overview/system-overview.md** | 3대 엔진(What-if, OLAP, See-Why), Phase 3.2/3.6/4, 포트 8400, 의존 모듈 |
| **01_architecture/architecture-overview.md** | 레이어(API·엔진·코어·데이터), 비동기 경계, 장애 격리, 디렉토리 구조 |
| **01_architecture/what-if-engine.md** | 시나리오 솔버, 민감도·전환점, 프로세스 시간축 시뮬레이션(Synapse 연동) |
| **01_architecture/olap-engine.md** | Mondrian XML, 피벗 쿼리, NL→피벗, ETL 동기화 |
| **01_architecture/root-cause-engine.md** | 인과 추론, SHAP, 반사실, Phase 4 |
| **02_api/analytics-api.md** | KPI 요약, 사건 추이, 이해관계자 분포, 성과율 추이, 재무 요약, 대시보드 |
| **02_api/olap-api.md** | 큐브 스키마 업로드, 피벗 쿼리, nl-query, 드릴스루, ETL sync/status |
| **02_api/what-if-api.md** | 시나리오 CRUD·compute·status·result·compare·sensitivity·breakeven·process-simulation |
| **02_api/root-cause-api.md** | 근본원인 분석·상태·목록·타임라인·반사실·impact·causal-graph·process-bottleneck |
| **03_backend/scenario-solver.md** | scipy.optimize, 목적함수·제약조건·의존 변수 |
| **03_backend/mondrian-parser.md** | Mondrian XML 파서·SQL 생성기 이식 |
| **03_backend/etl-pipeline.md** | Full/Incremental Sync, MV REFRESH, Airflow DAG |
| **03_backend/service-structure.md** | 서비스 계층·리포지토리 |
| **05_llm/nl-to-pivot.md** | 자연어→피벗 구조화 출력 |
| **06_data/database-schema.md** | what_if_scenarios, Materialized Views |
| **docs/02_api/service-endpoints-ssot.md** | Core→Vision 경로, Synapse 연동 |

> 위 문서는 **services/vision/docs/** 기준 상대 경로이다.

---

## 3. 갭 요약 (코드 기준)

| 영역 | 현재 상태 (코드) | Full 스펙 (설계 문서) |
|------|------------------|------------------------|
| **Analytics API** | **구현 완료**: `app/api/analytics_v3.py` GET 6개 엔드포인트, DB·스텁 폴백. 기존 POST /execute·/what-if는 analytics.py 유지. | analytics-api.md: GET /analytics/summary, /cases/trend, /stakeholders/distribution, /performance/trend, /cases/{id}/financial-summary, /dashboards |
| **OLAP 피벗** | **구현 완료**: POST /pivot/query는 pivot_engine으로 SQL 생성, vision_runtime.execute_pivot_query로 DB 실행(30초 타임아웃), 504 QUERY_TIMEOUT. columns·rows·aggregations·generated_sql 반환. | olap-api.md: Mondrian 메타→SQL 생성→MV 쿼리 실행, 30초 타임아웃, limit/offset·aggregations |
| **OLAP 큐브·스키마** | **구현 완료**: upload 시 mondrian_parser.parse_string 호출·검증, create_cube에 dimension_details·measure_details 저장. GET /cubes·/cubes/{name}은 vision_runtime.cubes. | mondrian-parser.md: Mondrian XML 파서 이식, fact_table·dimensions·measures 메타 추출 |
| **NL→피벗** | **구현 완료**: nl_to_pivot.translate(query, cube_context, cube_name_hint). OPENAI_API_KEY 있으면 OpenAI Chat Completions(json_object) 호출, 없으면 휴리스틱 스텁. interpreted_as로 pivot/query 동일 경로 실행, result·confidence·execution_time_ms 반환. | nl-to-pivot.md: LLM 구조화 출력으로 rows/columns/measures/filters 추출, 피벗 쿼리 실행 |
| **What-if 시나리오 계산** | **구현 완료**: `app/core/scenario_solver.py`에서 scipy.optimize SLSQP 사용, 목적함수·제약(legal_minimum, operating_fund, dscr)·60초 타임아웃. vision_runtime.run_scenario_solver 연동. | scenario-solver.md: scipy.optimize, 목적함수·제약조건·의존 변수, 60초 타임아웃 |
| **What-if 비동기 compute** | **구현 완료**: POST /compute → 202 + poll_url, 백그라운드 asyncio.to_thread(run_scenario_solver), GET /status에서 COMPUTING/COMPLETED/FAILED·progress_pct. | architecture-overview.md, what-if-api.md: compute는 비동기, 202 + poll_url, 60초 내 완료 목표 |
| **What-if 프로세스 시뮬레이션** | **구현 완료**: ProcessSimulationRequest를 process_model_id, scenario_name, description, parameter_changes(duration|resource|routing), sla_threshold_seconds로 정합. run_process_simulation에서 Synapse bottlenecks/performance 호출, original_cycle_time, simulated_cycle_time, by_activity, bottleneck_shift, affected_kpis, critical_path 반환. 502 SYNAPSE_UNAVAILABLE. | what-if-api.md §10: Synapse performance/bottlenecks/variants 연동, original_cycle_time, simulated_cycle_time, by_activity, bottleneck_shift |
| **ETL** | **구현 완료**: POST /etl/sync → 202 + sync_id, 백그라운드에서 target_views에 대해 REFRESH MATERIALIZED VIEW CONCURRENTLY 실행. GET /etl/status로 RUNNING/COMPLETED/FAILED, duration_seconds, rows_affected. 503 ETL_IN_PROGRESS. AIRFLOW_BASE_URL 설정 시 POST /etl/airflow/trigger-dag에서 Airflow REST API 호출. | etl-pipeline.md: Full/Incremental Sync, MV REFRESH CONCURRENTLY, Airflow DAG 트리거 |
| **ScenarioSolver** | **스텁**: `app/core/scenario_solver.py` — evaluate_what_if가 modifications 루프로 문자열 impact 반환, scipy·캐시 연동 없음. | scenario-solver.md: scipy 기반 제약 최적화, 목적함수·g(x)·h(x) |
| **Root Cause** | **구현됨**: root_cause_engine, vision_runtime 루트원인·반사실·process-bottleneck·메트릭(/health/ready, /metrics). Synapse 연동·오류코드 세분화는 S13 반영됨. | root-cause-api.md: POST/GET 엔드포인트, confidence_basis, process-bottleneck |
| **상태 저장** | **구현됨**: VisionStateStore(PostgreSQL 또는 SQLite fallback), what_if_scenarios·cubes·etl_jobs·root_cause_by_case 영속. | database-schema.md, architecture-overview.md |
| **디렉토리 구조** | **구현 완료**: app/engines/에 scenario_solver, mondrian_parser, pivot_engine, nl_to_pivot, etl_pipeline. API·services만 engines 참조, 엔진 간 import 없음. | architecture-overview.md: app/engines/(scenario_solver, mondrian_parser, pivot_engine, etl_service, nl_pivot_workflow, causal_engine) |

---

## 4. Phase 개요

| Phase | 목표 | 설계 문서 | 선행 | 상태 |
|-------|------|-----------|------|------|
| **V1** | Analytics API Full (KPI·추이·분포·재무·대시보드) | analytics-api.md | - | 완료 |
| **V2** | What-if scipy 솔버 + 비동기 compute + 프로세스 시뮬레이션 스펙 | scenario-solver.md, what-if-api.md, what-if-engine.md | - | 완료 |
| **V3** | OLAP Mondrian 파서·실제 SQL·MV 쿼리·NL→피벗·드릴스루 실연동 | olap-api.md, mondrian-parser.md, nl-to-pivot.md | DB·MV 스키마 확정 | 완료 (V3-1~V3-5) |
| **V4** | ETL 실동기화(Full/Incremental)·MV REFRESH·Airflow | etl-pipeline.md, olap-api.md | V3(큐브·MV 확정) | 완료 |
| **V5** | Root Cause Synapse 연동·오류코드 세분화 (선택) | root-cause-api.md | Root Cause 이미 구현됨 | 완료 (V5-1) |
| **V6** | (선택) 디렉토리 구조·엔진 레이어 정리 | architecture-overview.md | - | 완료 (V6-1, V6-2) |

---

## 5. Phase V1: Analytics API Full

**목표**: analytics-api.md에 정의된 6개 엔드포인트 구현. KPI 요약·사건 추이·이해관계자 분포·성과율 추이·개별 케이스 재무 요약·대시보드 위젯.

### 5.1 참조 설계

- **analytics-api.md**: GET /api/v3/analytics/summary(period, case_type), /analytics/cases/trend(granularity, from_date, to_date, group_by), /analytics/stakeholders/distribution(distribution_by), /analytics/performance/trend, /analytics/cases/{case_id}/financial-summary, /analytics/dashboards.
- **권한**: VIEWER 이상, Base URL /api/v3/analytics.

### 5.2 선행 조건

- Core 또는 공유 DB에서 cases·stakeholders·performance·financials 등 집계 소스 테이블 접근 가능. 없으면 Mock 데이터로 계약만 만족 가능.

### 5.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| V1-1 | GET /analytics/summary | period(YTD/MTD/QTD/LAST_YEAR/ALL), case_type 필터, kpis(total_cases, active_cases, total_obligations_amount, avg_performance_rate, avg_case_duration_days, stakeholder_satisfaction_rate), change_pct·prev_period_value. | analytics.py |
| V1-2 | GET /analytics/cases/trend | granularity(monthly/quarterly/yearly), from_date·to_date·case_type·group_by, series[].period, new_cases, completed_cases, active_cases, total_obligations_registered. | analytics.py |
| V1-3 | GET /analytics/stakeholders/distribution | distribution_by(stakeholder_type, stakeholder_class, amount_band, status), segments[].label, count, count_pct, amount, amount_pct, avg_satisfaction_rate. | analytics.py |
| V1-4 | GET /analytics/performance/trend | granularity, stakeholder_type·case_type 필터, series[].period, avg_performance_rate, secured_rate, general_rate, priority_rate, case_count. | analytics.py |
| V1-5 | GET /analytics/cases/{case_id}/financial-summary | financials, execution_progress, stakeholder_breakdown. 404 CASE_NOT_FOUND. | analytics.py |
| V1-6 | GET /analytics/dashboards | 대시보드 위젯 구성 반환. | analytics.py |

### 5.4 통과 기준 (Gate V1)

- 6개 엔드포인트가 analytics-api.md Request/Response·에러 코드와 일치한다. (데이터 소스가 없으면 Mock 응답으로 계약 테스트 통과 가능.)

---

## 6. Phase V2: What-if scipy 솔버 + 비동기 compute + 프로세스 시뮬레이션

**목표**: 시나리오 계산을 scipy.optimize 기반으로 전환, compute를 비동기(백그라운드 태스크)로 실행, 프로세스 시뮬레이션 API를 설계 스펙(process_model_id, parameter_changes, Synapse 연동)에 맞춘다.

### 6.1 참조 설계

- **scenario-solver.md**: 목적함수·제약조건(g_1, g_2, g_3, h_1), 결정 변수 벡터, scipy.optimize 메서드, 60초 타임아웃.
- **what-if-api.md**: POST /what-if/{id}/compute → 202 Accepted, poll_url, GET /status, GET /result. §10 process-simulation: process_model_id, parameter_changes(duration|resource|routing), Synapse performance/bottlenecks/variants.
- **architecture-overview.md**: compute는 비동기, 타임아웃 60초.

### 6.2 선행 조건

- (권장) V1 또는 독립적으로 진행 가능. Synapse process-mining API 스펙 확정 시 프로세스 시뮬레이션 연동.

### 6.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| V2-1 | scipy 기반 시나리오 솔버 | scenario_solver 또는 engines/scenario_solver에서 scipy.optimize 사용, 목적함수·제약조건·결정 변수 구현. constraints_met·is_feasible·feasibility_score 반영. | scenario_solver.py 또는 engines/ |
| V2-2 | compute 비동기화 | POST /what-if/{id}/compute에서 백그라운드 태스크 디스패치, 즉시 202 반환. GET /status에서 COMPUTING/COMPLETED/FAILED·progress_pct. 타임아웃 60초. | what_if.py, vision_runtime |
| V2-3 | 프로세스 시뮬레이션 요청 스키마 정합 | ProcessSimulationRequest를 process_model_id, scenario_name, description, parameter_changes(duration_change, resource_change, routing_probability), sla_threshold_seconds 로 변경. | what_if.py |
| V2-4 | 프로세스 시뮬레이션 Synapse 연동 | Synapse GET performance, bottlenecks, variants 호출. original_cycle_time, simulated_cycle_time, by_activity, bottleneck_shift, affected_kpis, critical_path 반환. 502 SYNAPSE_UNAVAILABLE. | vision_runtime 또는 별도 service |

### 6.4 통과 기준 (Gate V2)

- compute 호출 시 scipy 기반 결과가 저장되며, 제약조건 위반 시 is_feasible false·constraints_met 반영된다.
- compute는 202 반환 후 폴링으로 COMPLETED/FAILED를 확인할 수 있다.
- process-simulation 요청/응답이 what-if-api.md §10과 일치하며, Synapse 연동 시 실제 cycle time·병목 데이터를 반영한다.

---

## 7. Phase V3: OLAP Mondrian 파서·실제 SQL·MV 쿼리·NL→피벗

**목표**: Mondrian XML 파서 이식, 큐브 메타 기반 SQL 생성·실행(MV 쿼리), 쿼리 타임아웃 30초. NL→피벗은 LLM 구조화 출력으로 파라미터 추출 후 피벗 쿼리 실행.

### 7.1 참조 설계

- **mondrian-parser.md**: MondrianXMLParser.parse_file, factTable·dimensions·measures 추출. SQL 생성기(cube 메타→SELECT 생성).
- **olap-api.md**: POST /pivot/query → generated_sql 실제 실행, execution_time_ms, total_rows, columns, rows, aggregations. POST /pivot/nl-query → interpreted_as·result·confidence.
- **nl-to-pivot.md**: LLM 호출, dimensions·rows·columns·measures·filters 구조화 출력.
- **06_data**: mv_business_fact, mv_cashflow_fact, dim_* 테이블.

### 7.2 선행 조건

- 공유 DB에 Materialized View·dimension 테이블 존재 또는 마이그레이션으로 생성. OPENAI_API_KEY 등 LLM 설정(NL→피벗용).

### 7.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| V3-1 | Mondrian XML 파서 | MondrianXMLParser 또는 동등 모듈, parse_file(xml_path|content)→schema_name·cubes[].name, factTable, dimensions, measures. upload 시 파서 호출·검증. | mondrian_parser.py 또는 core/ |
| V3-2 | 큐브 메타→SQL 생성 | rows/columns/measures/filters를 받아 MV·dim 조인 SQL 생성. sort_by·sort_order·limit·offset. olap-api.md 필터 연산자(=, !=, in, not_in, >=, <=, between). | pivot_engine 또는 olap 서비스 |
| V3-3 | pivot/query 실제 실행 | 생성된 SQL을 DB에서 실행, 타임아웃 30초, MAX_ROWS 제한. columns·rows·aggregations 반환. 504 QUERY_TIMEOUT. | olap.py, vision_runtime 또는 엔진 |
| V3-4 | NL→피벗 LLM 연동 | nl_to_pivot.translate에서 LLM 구조화 출력 호출, cube_name·rows·columns·measures·filters 추출. 추출 결과로 pivot/query 동일 경로 실행. | nl_to_pivot.py, 05_llm 설정 |
| V3-5 | 드릴스루 실제 쿼리 | pivot/drillthrough에서 셀 좌표(차원 필터)로 원본 레코드 조회. cube_name·차원 파라미터·limit. | olap.py |

### 7.4 통과 기준 (Gate V3)

- 큐브 스키마 업로드 시 Mondrian 파서로 메타 추출·저장된다. pivot/query는 실제 SQL 실행 결과를 반환하며, Mock 행이 아니다. NL→피벗은 LLM 출력으로 파라미터가 추출되고 동일 쿼리 경로로 결과가 반환된다.

---

## 8. Phase V4: ETL 실동기화

**목표**: ETL sync 시 REFRESH MATERIALIZED VIEW CONCURRENTLY 실행(또는 동등), Full/Incremental 구분. Airflow DAG 트리거는 설정 시 실제 Airflow API 호출.

### 8.1 참조 설계

- **etl-pipeline.md**: Full Sync(전체 MV 갱신), Incremental Sync(변경분). REFRESH MATERIALIZED VIEW CONCURRENTLY. ETL sync 상태 RUNNING→COMPLETED/FAILED, rows_affected.
- **olap-api.md**: POST /etl/sync( sync_type, target_views, force), 202 Accepted. GET /etl/status(sync_id). POST /etl/airflow/trigger-dag.

### 8.2 선행 조건

- V3으로 MV·큐브 메타 확정. DB 사용자에게 MV REFRESH 권한 필요.

### 8.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| V4-1 | ETL sync 실제 MV REFRESH | queue_etl_job 시 백그라운드에서 target_views에 대해 REFRESH MATERIALIZED VIEW CONCURRENTLY 실행. 상태 COMPLETED/FAILED, duration_seconds, rows_affected. | vision_runtime, etl_pipeline 또는 engines |
| V4-2 | Full vs Incremental | sync_type full이면 전체 MV, incremental이면 변경분만(또는 문서화된 정책). 503 ETL_IN_PROGRESS. | etl_pipeline.md 정책 반영 |
| V4-3 | Airflow DAG 트리거 (선택) | AIRFLOW_URL 등 설정 시 POST /api/v1/dags/{dag_id}/dagRuns 호출. dag_run_id·state 반환. | olap.py, 설정 |

### 8.4 통과 기준 (Gate V4)

- POST /etl/sync 호출 시 MV가 실제로 갱신되며, GET /etl/status로 완료·소요 시간·rows_affected를 확인할 수 있다.

**구현 상태**: V4-1·V4-2·V4-3 반영. vision_runtime.run_etl_refresh_sync에서 ALLOWED_MV_VIEWS에 대해 REFRESH MATERIALIZED VIEW CONCURRENTLY 실행, 503 ETL_IN_PROGRESS, AIRFLOW_BASE_URL 설정 시 trigger-dag에서 Airflow REST API 호출.

---

## 9. Phase V5: Root Cause Synapse 연동·오류코드 (선택)

**목표**: Root Cause는 이미 구현됨. Synapse 연동 정규화·오류코드 세분화(INSUFFICIENT_PROCESS_DATA, PROCESS_MODEL_NOT_FOUND, SYNAPSE_UNAVAILABLE)가 문서와 일치하는지 검증 및 보완.

### 9.1 참조 설계

- **root-cause-api.md**: §8 process-bottleneck, Synapse bottlenecks/variants/performance. 에러 코드 404·422·502.

### 9.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| V5-1 | 오류코드·메시지 정합 | API가 404 PROCESS_MODEL_NOT_FOUND, 422 INSUFFICIENT_PROCESS_DATA, 502 SYNAPSE_UNAVAILABLE 반환하는지 확인. 사용자 표시 메시지 정리. | root_cause.py, vision_runtime |

### 9.3 통과 기준 (Gate V5)

- root-cause-api.md 에러 코드 표와 구현이 일치한다.

**구현 상태**: process-bottleneck에서 404 PROCESS_MODEL_NOT_FOUND, 422 INSUFFICIENT_PROCESS_DATA, 502 SYNAPSE_UNAVAILABLE 반환. root_cause.py에서 문서의 사용자 표시 메시지(한국어)로 detail.message 정합.

---

## 10. Phase V6: 디렉토리 구조·엔진 레이어 (선택)

**목표**: architecture-overview.md의 app/engines/ 구조로 이동·정리. 엔진 간 직접 import 금지 유지.

### 10.1 참조 설계

- **architecture-overview.md**: app/engines/(scenario_solver, mondrian_parser, pivot_engine, etl_service, nl_pivot_workflow, causal_engine). API 레이어에서만 엔진 조합.

### 10.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| V6-1 | engines 디렉토리 생성·이동 | scenario_solver, mondrian_parser, pivot_engine, nl_pivot_workflow, etl_service를 app/engines/로 이동 또는 신규 작성. core/에 config·database·auth 유지. | app/engines/ |
| V6-2 | API→엔진 의존만 허용 | API 라우터가 engines·services 호출. engines 간 상호 import 없음. | import 정리 |

### 10.3 통과 기준 (Gate V6)

- 금지 의존(역방향 import, 엔진 간 직접 호출) 0건. 기존 테스트 통과.

**구현 상태**: app/engines/ 생성. scenario_solver, mondrian_parser, pivot_engine, nl_to_pivot, etl_pipeline을 core/에서 engines/로 이동. API(olap, what_if)·services(vision_runtime)만 engines 참조. 엔진 간 import 없음. 29개 단위 테스트 통과.

---

## 11. 권장 실행 순서

1. **Phase V1 (Analytics API)** — 대시보드·KPI 계약이 우선일 때. 데이터 소스 없으면 Mock으로 계약만 충족 가능.
2. **Phase V2 (What-if)** — scipy 솔버·비동기 compute·프로세스 시뮬레이션 스펙이 핵심일 때.
3. **Phase V3 (OLAP)** — 피벗·NL 쿼리 실데이터 필요 시. MV·dim 스키마 확정 선행.
4. **Phase V4 (ETL)** — V3 이후 MV 갱신 자동화.
5. **Phase V5, V6** — 정책·리팩터링 여유 시.

---

## 12. 문서 갱신

- 각 Phase 완료 시 **future-implementation-backlog.md** §3 Vision 항목을 코드 재검증 후 갱신.
- **services/vision/docs/02_api/** 의 "구현 상태 태그"·Partial 표기를 구현 상태에 맞게 수정.
- **98_gate-pass-criteria.md** Gate V1~V3 통과 여부를 구현 계획과 연동.
