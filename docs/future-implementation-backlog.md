# 향후 구현 백로그 (코드 기준 현행화)

> **기준**: 실제 구현된 코드만 조사. Core(스텁/예정 파일), Canvas(비적용 항목).  
> **갱신**: 2026-02-22

---

## 1. Core (services/core) — 코드 검증 결과

> **갱신**: 2026-02. 구현 계획서: [docs/implementation-plans/core/01_core-fullspec-implementation-plan.md](implementation-plans/core/01_core-fullspec-implementation-plan.md). Phase G·H·I·J·K·L·M·N 반영. H: 멀티스텝 러너 구현, 노드 내부 서비스 연동 전.

### 1.1 Domain·BPM

| 항목 | 파일 (검증됨) | 코드 상 상태 |
|------|----------------|---------------|
| **BPMN/DMN 추출기** | `app/bpm/extractor.py` | **구현됨(최소)**: 파일 검증·pdfplumber 텍스트·청킹·스텁 반환. LLM Entity/BPMN/DMN 연동은 추후. |
| **Saga 보상** | `app/bpm/saga.py` | **구현됨**: 역순 조회·보상 단계 생성·실행, _execute_compensation(MCP), _update_process_status, _publish_event(SAGA_COMPENSATION_COMPLETED). 보상 실패 알림은 로깅. |
| **LangGraph 오케스트레이터** | `app/orchestrator/langgraph_flow.py` | **멀티스텝 러너 + Oracle/Synapse 연동**: route→intent별 노드(process/document/query/mining)→hitl→complete. query_data: Oracle `POST {ORACLE_BASE_URL}/text2sql/ask`(question, datasource_id, options). mining: state에 case_id·log_id 있을 때 Synapse `POST .../process-mining/discover`. URL·계약 SSOT: `docs/service-endpoints-ssot.md` §2.1. |
| **에이전트 지식 학습 루프** | `app/orchestrator/agent_loop.py` | **구현됨**: graph.ainvoke 호출, SUBMITTED/DONE 반환. HITL 시 needs_human_review. |
| **MCP 클라이언트** | `app/orchestrator/mcp_client.py` | **구현됨**: execute_mcp_tool(MCP_BASE_URL·httpx). SafeToolLoader/테넌트 격리는 선택. |

**참고**: `app/bpm/engine.py`는 `get_initial_activity`, `get_next_activities_after` 구현됨(스텁 아님). `process_service`가 이 계층 호출. Workers 경로는 `app/workers/` (sync, watch_cep, event_log, base, event_log_parsers).

### 1.2 Workers

| Worker | 파일 존재 | 코드 상 상태 |
|--------|------------|---------------|
| **sync** | `app/workers/sync.py` | (동작 검증 생략) |
| **watch_cep** | `app/workers/watch_cep.py` | **구현됨**: CEP 룰 평가(_evaluate_rule), WatchService.create_alert, idempotency 24h, _send_alert_channels(인앱=DB; 이메일/SMS/Slack 어댑터 미구현 시 로깅). |
| **event_log** | `app/workers/event_log.py` | **구현됨**: MinIO 다운로드, validate_xes/validate_csv, Synapse ingest(multipart), _report_progress·_publish_completion·_report_failure. |
| **ocr** | `app/workers/ocr.py` | **구현됨(스켈레톤)**: axiom:workers 소비·ACK, WORKER_OCR_REQUEST 처리. MinIO·Vision 파이프라인 추후. |
| **extract** | `app/workers/extract.py` | **구현됨(스켈레톤)**: WORKER_EXTRACT_REQUEST 소비·ACK. 청킹·LLM·pgvector 추후. |
| **generate** | `app/workers/generate.py` | **구현됨(스켈레톤)**: WORKER_GENERATE_REQUEST 소비·ACK. LLM·MinIO 추후. |

### 1.3 API·라우팅

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **users** | `app/api/users/routes.py` | **구현됨**: GET /me, POST /users(생성), GET /users(목록). admin 또는 user:manage·tenant 제한. |
| **인증** | `app/main.py` | `auth_router`, `users_router`, `process_router`, `watch_router`, `agent_router`, `gateway_router`, `events_router`, **cases_router** 포함. |
| **app/api/cases/** | `app/api/cases/routes.py` | **구현됨**: GET /api/v1/cases(목록·페이징·total), GET /api/v1/cases/activities, POST /api/v1/cases/:caseId/documents/:docId/review. core_case, core_case_activity, core_document_review 모델·테이블. |
| **속도 제한 미들웨어** | `app/core/rate_limiter.py`, `app/main.py` | **구현됨**: RateLimitMiddleware, 경로별 제한(login 10/분, agents 20/분, 기본 100/분). |

### 1.4 DB·스키마

- `users.preferences` 등: 코드베이스 내 스키마 정의 파일을 이번에 조사하지 않음. 문서 기준 항목이므로 생략.

---

## 2. Canvas (apps/canvas) — 코드 검증 결과

### 2.1 라우팅

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **createBrowserRouter** | `src/App.tsx` | `react-router-dom`에서 `BrowserRouter`, `Routes`, `Route`, `Navigate`만 import. `createBrowserRouter` 미사용 (L3, L47). |

### 2.2 i18n

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **react-i18next / useTranslation** | `package.json`, `src/**` grep | `package.json`에 `react-i18next` 없음. 소스에서 `i18n`, `useTranslation` 검색 0건. |

### 2.3 Design Tokens·다크 모드

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **전역 테마/토큰** | `src/index.css`, `src/**` | `index.css`에 `color-scheme: light dark` 만 존재. 테마 토큰·다크 전환용 전역 상태/컨텍스트 없음. |
| **Monaco / DiffViewer** | `src/**` grep | `DocumentEditorPage.tsx`에서 Monaco `theme="vs-dark"` 하드코딩. `DocumentDiffViewer.tsx`에서 `useDarkTheme` 등 로컬 다크 사용. 전역 디자인 토큰·다크 모드 스위치 미구현. |

### 2.4 프로세스 디자이너

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **Minimap / PropertyPanel / Yjs / ConformanceOverlay / VariantList** | `src/**` grep | 전체 0건. `ProcessDesignerPage.tsx`는 `react-konva`(Stage, Layer, Rect, Text, Group), `processDesignerStore`, `localStorage`(BOARD_STORAGE_PREFIX)만 사용. |

### 2.5 단위·통합 테스트

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **Vitest / @testing-library** | `package.json` | `devDependencies`에 `vitest`, `@testing-library/*`, `jest` 없음. `@playwright/test` 만 존재. |

### 2.6 디렉터리 구조

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **app/ 디렉터리** | `src/` 구조 | `App.tsx`, `main.tsx`가 `src/` 직하위. `src/app/` 디렉터리 없음. |
| **shared/ui** | `src/` | `shared/components/` 존재. `shared/ui/` 없음. UI 컴포넌트는 `src/components/ui/` (button, card, input, select 등 9개). |

### 2.7 이벤트·스트림

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **WebSocket** | `src/**` grep | `new WebSocket` 호출 없음. `watchStream.ts`에서만 `EventSource` 사용(SSE). `useAlerts.ts` 주석 "WebSocket / SSE Simulation" (실제 연결은 SSE). |

### 2.8 페이지·접근성

| 항목 | 검증 방법 | 결과 |
|------|-----------|------|
| **온톨로지 테이블 뷰** | `src/pages/ontology/OntologyPage.tsx` | `isTableMode`일 때 "접근성을 위한 테이블 뷰 (구현 예정)" 문구만 렌더 (L64–66). 테이블 뷰 로직 미구현. |

---

## 3. 기타 서비스 (문서 기준, 코드 미검증)

Synapse, Vision, Oracle, Weaver는 이번에 **코드 스캔하지 않음**. 문서상 “예정”/“Stub”/“향후”만 참고 시 아래 문서를 사용.

- Synapse: `docs/full-spec-gap-analysis-2026-02-22.md`, `services/synapse/docs/02_api/process-mining-api.md`
- Vision: `services/vision/docs/01_architecture/architecture-overview.md`
- Oracle: `services/oracle/docs/06_data/query-history.md`, `migration-from-kair.md`. **구현 현행**: NL2SQL/ReAct Full·JWT·Rate limit·품질 게이트·Canvas oracleApi 통일은 `docs/implementation-plans/oracle/01_oracle-fullspec-implementation-plan.md`(Phase O1–O6 완료) 참조.
- Weaver: `services/weaver/docs/01_architecture/metadata-service.md`, `neo4j-schema-v2.md`. **구현 현행**: extract-metadata SSE·Neo4j 저장·FK 추출·Oracle 어댑터 등은 `docs/implementation-plans/weaver/01_weaver-fullspec-implementation-plan.md`(Phase W1–W9 완료) 참조.

---

## 4. 참조 문서

| 문서 | 용도 |
|------|------|
| `docs/core-docs-vs-implementation-gap.md` | Core 문서 대비 갭 상세. |
| `docs/implementation-plans/frontend/00_ui-ux-gap-implementation-plan.md` §6 | 프론트 비적용 범위·갭 잔여. |
| `docs/implementation-plans/core/00_core-gap-implementation-plan.md` | Core Phase D/E, Worker 예정. |
| `apps/canvas/docs/04_frontend/event-streams.md` | Watch SSE vs POST 스트림, WebSocket 미사용 명시. |

---

**정리**: §1·§2는 **실제 코드(파일 존재 여부, 함수 내용, import, package.json)**만 기준으로 현행화함. §3은 문서 기준이며, 필요 시 해당 서비스 코드를 같은 방식으로 조사해 반영하면 된다.
