# Planned 엔드포인트 구현 우선순위 백로그

기준일: 2026-02-21  
대상: `services/*/docs/02_api/*.md`의 `상태=Planned` 엔드포인트

---

## 1. 우선순위 기준

- `P0`: 현재 사용자 흐름/운영 리스크를 즉시 줄여야 하는 항목
- `P1`: 핵심 도메인 기능 완성을 위해 다음 스프린트에서 필요한 항목
- `P2`: 확장 기능/고도화 항목

---

## 2. P0 (즉시 착수)

### P0-CORE-WATCH-BASE

- 서비스: Core
- 목적: Canvas 알림 기능 복구
- 엔드포인트
  - `GET /api/v1/watches/alerts`
  - `PUT /api/v1/watches/alerts/{id}/acknowledge`
  - `PUT /api/v1/watches/alerts/read-all`
  - `GET /api/v1/watches/stream`
- 근거 문서
  - `services/core/docs/02_api/watch-api.md`
  - `docs/implementation-plans/core/90_sprint7-ticket-board.md`
- 이유
  - 프론트 호출 경로가 이미 존재하므로(Watch 화면) 실패 영향이 즉시 발생

### P0-CORE-WATCH-SUBSCRIPTION

- 서비스: Core
- 목적: 알림 규칙/구독 관리 최소 완성
- 엔드포인트
  - `POST /api/v1/watches/subscriptions`
  - `GET /api/v1/watches/subscriptions`
  - `PUT /api/v1/watches/subscriptions/{id}`
  - `DELETE /api/v1/watches/subscriptions/{id}`
  - `POST /api/v1/watches/rules`
  - `GET /api/v1/watches/rules`
- 근거 문서
  - `services/core/docs/02_api/watch-api.md`
  - `docs/implementation-plans/core/90_sprint7-ticket-board.md`

### P0-CORE-PROCESS-ESSENTIAL

- 서비스: Core
- 목적: `/submit` 외 프로세스 기본 lifecycle 복원
- 엔드포인트
  - `POST /api/v1/process/initiate`
  - `GET /api/v1/process/{proc_inst_id}/status`
  - `GET /api/v1/process/{proc_inst_id}/workitems`
  - `POST /api/v1/process/approve-hitl`
  - `POST /api/v1/process/rework`
- 근거 문서
  - `services/core/docs/02_api/process-api.md`
  - `docs/implementation-plans/core/95_sprint2-ticket-board.md`

---

## 3. P1 (다음 스프린트)

### P1-SYNAPSE-EVENTLOG

- 서비스: Synapse
- 목적: 이벤트 로그 수집/조회 기반 구축
- 엔드포인트
  - `POST /ingest`
  - `GET /`
  - `GET /{log_id}`
  - `GET /{log_id}/preview`
  - `GET /{log_id}/statistics`
  - `PUT /{log_id}/column-mapping`
  - `POST /{log_id}/refresh`
  - `DELETE /{log_id}`
- 근거 문서
  - `services/synapse/docs/02_api/event-log-api.md`
  - `docs/implementation-plans/synapse/94_sprint3-ticket-board.md`

### P1-SYNAPSE-EXTRACTION

- 서비스: Synapse
- 목적: 비정형 추출 파이프라인 실제화
- 엔드포인트
  - `POST /documents/{doc_id}/extract-ontology`
  - `GET /documents/{doc_id}/ontology-status`
  - `GET /documents/{doc_id}/ontology-result`
  - `PUT /ontology/{entity_id}/confirm`
  - `POST /cases/{case_id}/ontology/review`
  - `GET /cases/{case_id}/review-queue`
  - `POST /documents/{doc_id}/retry`
  - `POST /documents/{doc_id}/revert-extraction`
- 근거 문서
  - `services/synapse/docs/02_api/extraction-api.md`
  - `docs/implementation-plans/synapse/94_sprint3-ticket-board.md`

### P1-SYNAPSE-SCHEMA-EDIT

- 서비스: Synapse
- 목적: NL2SQL 보조를 위한 스키마 수동 편집 경로 확보
- 엔드포인트
  - `/tables`, `/tables/{table_name}`
  - `/tables/{table_name}/description`
  - `/columns/{table_name}/{column_name}/description`
  - `/relationships` (GET/POST/DELETE)
  - `/tables/{table_name}/embedding`
  - `/batch-update-embeddings`
- 근거 문서
  - `services/synapse/docs/02_api/schema-edit-api.md`
  - `docs/implementation-plans/synapse/94_sprint3-ticket-board.md`

### P1-ORACLE-META

- 서비스: Oracle
- 목적: Text2SQL 메타 탐색 기능 제공
- 엔드포인트
  - `/text2sql/meta/tables`
  - `/text2sql/meta/tables/{name}/columns`
  - `/text2sql/meta/datasources`
  - `/text2sql/meta/tables/{name}/description`
  - `/text2sql/meta/columns/{fqn}/description`
- 근거 문서
  - `services/oracle/docs/02_api/meta-api.md`
  - `docs/implementation-plans/oracle/95_sprint2-ticket-board.md`

### P1-CORE-GATEWAY-PROXY

- 서비스: Core
- 목적: 외부 단일 진입점 복구 (event-log/process-mining 프록시)
- 엔드포인트
  - `/api/v1/event-logs/*` 전 구간
  - `/api/v1/process-mining/*` 전 구간
- 근거 문서
  - `services/core/docs/02_api/gateway-api.md`
  - `docs/implementation-plans/core/96_sprint1-ticket-board.md`

---

## 4. P2 (고도화)

### P2-VISION-WHATIF-FULL

- 서비스: Vision
- 목적: What-if CRUD/계산/비교 전 구간 완성
- 엔드포인트
  - `/what-if`
  - `/what-if/{scenario_id}`
  - `/what-if/{scenario_id}/compute`
  - `/what-if/{scenario_id}/status`
  - `/what-if/{scenario_id}/result`
  - `/what-if/compare`
  - `/what-if/{scenario_id}/sensitivity`
  - `/what-if/{scenario_id}/breakeven`
  - `/what-if/process-simulation`
- 근거 문서
  - `services/vision/docs/02_api/what-if-api.md`
  - `docs/implementation-plans/vision/92_sprint5-ticket-board.md`

### P2-VISION-OLAP

- 서비스: Vision
- 목적: 큐브/피벗/ETL API 구현
- 엔드포인트
  - `/cubes/schema/upload`
  - `/cubes`
  - `/cubes/{cube_name}`
  - `/pivot/query`
  - `/pivot/nl-query`
  - `/pivot/drillthrough`
  - `/etl/analyze`
  - `/etl/sync`
  - `/etl/status`
  - `/etl/airflow/trigger-dag`
- 근거 문서
  - `services/vision/docs/02_api/olap-api.md`
  - `docs/implementation-plans/vision/92_sprint5-ticket-board.md`

### P2-WEAVER-DATASOURCE-QUERY

- 서비스: Weaver
- 목적: 데이터소스/쿼리 API 확장
- 엔드포인트
  - Datasource: `/api/datasources/*` (types/list/detail/update/health/test/schema/sample)
  - Query: `/api/query/*` (status/materialized/models/jobs/knowledge-bases 포함)
- 근거 문서
  - `services/weaver/docs/02_api/datasource-api.md`
  - `services/weaver/docs/02_api/query-api.md`
  - `docs/implementation-plans/weaver/95_sprint2-ticket-board.md`
  - `docs/implementation-plans/weaver/94_sprint3-ticket-board.md`

### P2-WEAVER-METADATA-CATALOG

- 서비스: Weaver
- 목적: 메타데이터 카탈로그/스냅샷/태깅/통계 API 구현
- 엔드포인트
  - `/api/v1/metadata/*` 전 구간
- 근거 문서
  - `services/weaver/docs/02_api/metadata-catalog-api.md`
  - `docs/implementation-plans/weaver/94_sprint3-ticket-board.md`

### P2-ORACLE-EVENTS

- 서비스: Oracle (중장기 Core Watch 이관 전제)
- 목적: 이벤트 룰/스케줄/SSE/watch-agent API 구현 또는 Core로 완전 이관
- 엔드포인트
  - `/text2sql/events/*`
  - `/text2sql/watch-agent/chat`
- 근거 문서
  - `services/oracle/docs/02_api/events-api.md`
  - `docs/implementation-plans/oracle/90_sprint7-ticket-board.md`

### P2-CORE-AGENT-MCP

- 서비스: Core
- 목적: Agent/MCP/Completion API 구현
- 엔드포인트
  - `/api/v1/agents/*`
  - `/api/v1/completion/*`
  - `/api/v1/mcp/*`
- 근거 문서
  - `services/core/docs/02_api/agent-api.md`
  - `docs/implementation-plans/core/93_sprint4-ticket-board.md`

---

## 5. 실행 권고

1. P0 3개 번들을 먼저 티켓화하고, 완료 기준을 “문서 체크”가 아닌 “라우트 + 계약 테스트 + e2e”로 고정
2. P1은 Synapse(Event-log/Extraction)와 Oracle Meta를 우선 연결하여 Core Gateway 프록시 경로를 실사용 가능 상태로 전환
3. P2는 Vision/Weaver 확장 기능으로 묶어 병렬 추진

---

## 6. 상태 업데이트 (2026-02-22)

### 6.0 P0 구현 상태

- [x] `P0-CORE-WATCH-BASE` 완료
  - 구현: `services/core/app/api/watch/routes.py`
  - 테스트: `services/core/tests/integration/test_e2e_watch_api.py`
- [x] `P0-CORE-WATCH-SUBSCRIPTION` 완료
  - 구현: `services/core/app/api/watch/routes.py`, `services/core/app/services/watch_service.py`
  - 테스트: `services/core/tests/integration/test_e2e_watch_api.py`
- [x] `P0-CORE-PROCESS-ESSENTIAL` 완료
  - 구현: `services/core/app/api/process/routes.py`, `services/core/app/services/process_service.py`
  - 테스트:
    - `services/core/tests/integration/test_e2e_process_lifecycle.py`
    - `services/core/tests/integration/test_e2e_process_submit.py`

### 6.1 P1 구현 상태

- [x] `P1-SYNAPSE-EVENTLOG` 완료
  - 구현: `services/synapse/app/api/event_logs.py`
  - 테스트: `services/synapse/tests/unit/test_event_log_api.py`
- [x] `P1-SYNAPSE-EXTRACTION` 완료
  - 구현: `services/synapse/app/api/extraction.py`
  - 테스트: `services/synapse/tests/unit/test_extraction_api_full.py`
- [x] `P1-SYNAPSE-SCHEMA-EDIT` 완료
  - 구현: `services/synapse/app/api/schema_edit.py`
  - 테스트: `services/synapse/tests/unit/test_schema_edit_api.py`
- [x] `P1-ORACLE-META` 완료
  - 구현: `services/oracle/app/api/meta.py`
  - 테스트: `services/oracle/tests/unit/test_meta_api.py`
- [x] `P1-CORE-GATEWAY-PROXY` 완료 (EventLog/ProcessMining/Extraction/Schema-Edit/Graph/Ontology)
  - 구현: `services/core/app/api/gateway/routes.py`
  - 단위 테스트: `services/core/tests/unit/test_gateway_routes.py`
  - 라이브 E2E:
    - `services/core/tests/integration/test_e2e_gateway_eventlog_mining_live.py`
    - `services/core/tests/integration/test_e2e_gateway_extraction_schema_live.py`
    - `services/core/tests/integration/test_e2e_gateway_graph_ontology_live.py`

### 6.2 잔여 우선순위 (Full Spec 기준, 2026-02-22 갱신)

아래 항목은 라우트 존재/단위 테스트 통과와 별개로, `실연동·운영·아키텍처 정책` 기준에서 잔여다.  
근거: `docs/full-spec-gap-analysis-2026-02-22.md`

- `P0-FULLSPEC-VISION-ROOTCAUSE`
  - 상태: In Progress (최소 API 1차 완료)
  - 범위: `/api/v3/cases/{case_id}/root-cause-analysis*`, `/counterfactual` 최소 구현
- `P0-FULLSPEC-CANVAS-AUTH`
  - 상태: In Progress (인증 1차 완료)
  - 범위: mock 인증 경로 제거, refresh token 실구현, ProtectedRoute 강제 인증
- `P0-FULLSPEC-SSOT-SYNC`
  - 상태: In Progress (자동검증 1차 완료)
  - 범위: `docs/service-endpoints-ssot.md`와 `docker-compose.yml`, `k8s/*.yaml` 정합화
- `P1-FULLSPEC-ORACLE-NL2SQL-REAL`
  - 상태: In Progress (mock-to-real 1차 완료)
  - 범위: NL2SQL mock pipeline 제거 및 실제 SQL 생성/실행 경로 강화
- `P1-FULLSPEC-VISION-PERSISTENCE`
  - 상태: In Progress (영속화 1차 완료)
  - 범위: what-if/olap/etl 상태의 in-memory 저장소를 영속 저장소로 전환
- `P1-FULLSPEC-CORE-AGENT-PERSISTENCE`
  - 상태: In Progress (영속화 1차 완료)
  - 범위: Agent feedback/knowledge/MCP 상태 DB 영속화
- `P1-FULLSPEC-SYNAPSE-CONFORMANCE`
  - 상태: Planned
  - 범위: conformance checker stub 제거 및 실제 계산 경로 연결
- `P1-FULLSPEC-OUTBOX-STREAMS`
  - 상태: Implemented (1차 운영 경로 완료)
  - 범위: Outbox -> Redis Streams publisher/consumer 운영 경로 명시 및 증적화
- `P2-FULLSPEC-SELF-VERIFICATION`
  - 상태: Implemented (1차 정책 런타임 적용)
  - 범위: 20% 샘플링 self-check validator, fail routing, KPI 수집
- `P2-FULLSPEC-4SOURCE-LINEAGE`
  - 상태: Implemented (1차 계약 강제)
  - 범위: `source_origin/lineage_path/idempotency_key` 필수 메타 강제
- `P2-FULLSPEC-DOMAIN-CONTRACT-ENFORCEMENT`
  - 상태: Implemented (1차 런타임 검증)
  - 범위: Domain Event Contract Registry 런타임 검증(이벤트명/버전/키 규칙)
