# NL2SQL + 온톨로지 뷰 갭 분석 — 의미 기반 질의 엔진 진화 설계서

> **작성일**: 2026-02-24
> **상태**: Draft
> **문서 번호**: 04d (canvas 시리즈)
> **관련 문서**: `04a_frontend-implementation-plan-detailed.md`, `04b_ui-ux-gap`, `04c_ui-ux-improvement`
> **참조 설계**: `services/oracle/docs/02_api/text2sql-api.md`, `canvas/docs/04_frontend/nl2sql-chat.md`

---

## 전략적 비전: 인지 계층 고도화

### 이 문서의 본질

이 문서는 단순 기능 목록이 아니라 **"NL2SQL을 의미 기반 질의 엔진으로 진화시키는 설계서"**다.

현재 NL2SQL 파이프라인은 키워드 매칭 수준에서 동작한다:

```
자연어 → 테이블 검색(하드코딩) → SQL 생성
```

이 문서의 구현 계획이 완성되면:

```
자연어 → 개념 그래프 탐색 → 의미 해석 → 구조 매핑 → SQL 생성
```

이 차이는 SQL 정확도, hallucination 감소, 도메인 적합성에서 **질적 전환**을 만든다.

### 인지 계층 다이어그램

```
Layer 4: 거버넌스     ← O5 (품질·버전·HITL)
Layer 3: 영향 인지     ← O4 (cross-domain 변경 영향 분석)
Layer 2: 의미 인지     ← O3 (개념→구조 매핑 자동화) ← 🔴 핵심
Layer 1: 스키마 인지   ← O1~O2 (실제 Neo4j 그래프 탐색)
Layer 0: 키워드 매칭   ← 현재 (하드코딩 테이블 검색)
```

### Phase별 시스템 지능 향상도

| Phase | 인지 계층 | 지능 향상도 | 위험도 | 전략적 중요도 |
| --- | --- | --- | --- | --- |
| O1 | Layer 1 | 낮음 (UI 연결) | 낮음 | 필수 전제 |
| O2 | Layer 1 | 중간 (매핑 생성) | 중간 | 매우 중요 |
| O3 | Layer 2 | 매우 높음 (NL2SQL 뇌 업그레이드) | 높음 | **핵심** |
| O4 | Layer 3 | 분석력 강화 | 중간 | 중요 |
| O5 | Layer 4 | 거버넌스 | 낮음 | 후순위 |

---

## Part I — NL2SQL 갭 분석

### 1. 목적 및 범위

NL2SQL 설계 문서(`text2sql-api.md`, `nl2sql-pipeline.md`, `nl2sql-chat.md`)와 실제 구현(BE Oracle + FE Canvas) 간 3자 비교를 수행하여, 73개 갭 항목을 식별하고 단계별 구현 방안을 제시한다.

**비교 대상:**

| 계층 | 소스 | 비고 |
| --- | --- | --- |
| 설계 문서 | `services/oracle/docs/02_api/text2sql-api.md` | API 스펙 |
| 설계 문서 | `services/oracle/docs/01_architecture/nl2sql-pipeline.md` | 파이프라인 아키텍처 |
| 설계 문서 | `canvas/docs/04_frontend/nl2sql-chat.md` | FE 인터페이스 설계 |
| BE 구현 | `services/oracle/app/` | Oracle 서비스 (1,096 lines) |
| FE 구현 | `canvas/src/pages/nl2sql/` + `features/nl2sql/` | Canvas NL2SQL (806 lines) |

### 2. 참조 문서

| 문서 | 경로 | 용도 |
| --- | --- | --- |
| Text2SQL API Spec | `services/oracle/docs/02_api/text2sql-api.md` | API 계약 |
| NL2SQL Pipeline Architecture | `services/oracle/docs/01_architecture/nl2sql-pipeline.md` | 파이프라인 설계 |
| NL2SQL Chat Interface | `canvas/docs/04_frontend/nl2sql-chat.md` | FE 설계 |
| Meta API Spec | `services/oracle/docs/02_api/meta-api.md` | 메타데이터 API |
| Oracle Fullspec | `docs/03_implementation/oracle/01_oracle-fullspec-implementation-plan.md` | 전체 스펙 |
| Canvas Frontend Detailed | `docs/03_implementation/canvas/04a_frontend-implementation-plan-detailed.md` | FE 상세 |

### 3. 현황 요약

> **2026-02-25 업데이트**: P1~P5 + O1~O5 전체 Phase 구현 완료. Docker E2E 14/14 PASS.

| 구분 | 항목 수 | 완전 구현 (✅) | 부분 구현 (⚠️) | 미구현 (❌) | 비고 |
| --- | --- | --- | --- | --- | --- |
| A. 아키텍처·라우팅 | 8 | 7 (88%) | 1 (13%) | 0 (0%) | A1 prefix 미적용(의도적) |
| B. 요청 스키마 | 9 | 9 (100%) | 0 (0%) | 0 (0%) | |
| C. 응답 스키마 | 15 | 14 (93%) | 1 (7%) | 0 (0%) | |
| D. ReAct 스트리밍 | 4 | 4 (100%) | 0 (0%) | 0 (0%) | |
| E. 인증/인가 | 5 | 5 (100%) | 0 (0%) | 0 (0%) | |
| F. 차트 추천 | 7 | 7 (100%) | 0 (0%) | 0 (0%) | |
| G. 프론트엔드 전용 | 15 | 15 (100%) | 0 (0%) | 0 (0%) | |
| H. 백엔드 전용 | 10 | 10 (100%) | 0 (0%) | 0 (0%) | |
| **합계** | **73** | **71 (97%)** | **2 (3%)** | **0 (0%)** | 문서 현행화 잔여 |

### 4. 재사용 가능 기존 컴포넌트 (16개)

| # | 컴포넌트 | 파일 경로 | 해결하는 갭 |
| --- | --- | --- | --- |
| 1 | DataTable | `components/shared/DataTable.tsx` | G15 ResultTable |
| 2 | ChartSwitcher | `features/olap/components/ChartSwitcher.tsx` | G11 탭 전환 |
| 3 | EmptyState | `shared/components/EmptyState.tsx` | G3 빈 상태 |
| 4 | ErrorState | `shared/components/ErrorState.tsx` | G12, G13 에러 |
| 5 | ListSkeleton | `shared/components/ListSkeleton.tsx` | 로딩 상태 |
| 6 | Select (Shadcn) | `components/ui/select.tsx` | G1 DatasourceSelector |
| 7 | MonacoEditor | `react-monaco-editor` (의존성) | G7 SQL 수정 |
| 8 | usePermission | `shared/hooks/usePermission.ts` | E2 RBAC |
| 9 | RoleGuard | `shared/components/RoleGuard.tsx` | E2 라우트 가드 |
| 10 | sonner toast | 프로젝트 전역 | 피드백 UX |
| 11 | SyncProgress | `features/datasource/components/SyncProgress.tsx` | D4 타임라인 참조 |
| 12 | MessageBubble | `pages/nl2sql/components/MessageBubble.tsx` | G4 (존재, 미사용) |
| 13 | SqlPreview | `pages/nl2sql/components/SqlPreview.tsx` | G5 (존재, 미사용) |
| 14 | ThinkingIndicator | `pages/nl2sql/components/ThinkingIndicator.tsx` | G6 (존재, 미사용) |
| 15 | useNl2sqlMock | `features/nl2sql/hooks/useNl2sqlMock.ts` | 상태 전이 참조 |
| 16 | SchemaExplorer | `features/datasource/components/SchemaExplorer.tsx` | G1 참조 |

### 5. 갭 분석 상세 (73개 항목)

#### 5.1 아키텍처·라우팅 (A1-A8)

| ID | 갭 | 설계 문서 | BE 실제 | FE 실제 | 판정 |
| --- | --- | --- | --- | --- | --- |
| A1 | API 경로 프리픽스 | `/api/v1/text2sql/*` | `/text2sql/*` (main.py에 직접 mount) | `/text2sql/*` 호출 | ⚠️ 설계와 불일치 |
| A2 | CORS 설정 | 명시적 허용 도메인 | FastAPI CORSMiddleware (main.py) | 해당 없음 | ⚠️ 확인 필요 |
| A3 | Rate Limiting | /ask 30/60s, /react 10/60s | `rate_limit_ask()` 등 의존성 주입 (text2sql.py) | 429 에러 핸들링 없음 | ⚠️ FE 미처리 |
| A4 | Health Check | `GET /health` | main.py에 존재 | 해당 없음 | ✅ 구현됨 |
| A5 | API 버전관리 | v1 prefix | 없음 (직접 mount) | 없음 | ⚠️ 미적용 |
| A6 | 에러 응답 포맷 | `{code, message, details}` | 에러 코드 구현 (QUESTION_TOO_SHORT 등) | generic 에러 표시만 | ⚠️ FE 에러 코드 미활용 |
| A7 | 요청 유효성 검사 | question min 2, max 2000 | Pydantic min_length/max_length | Zod non-empty만 (max 없음) | ⚠️ FE 검증 불완전 |
| A8 | Meta API 통합 | `/text2sql/meta/*` 5개 엔드포인트 | meta.py 5개 엔드포인트 구현됨 | 미통합 (하드코딩 datasource_id) | ❌ FE 미통합 |

#### 5.2 요청 스키마 (B1-B9)

| ID | 갭 | 설계 문서 | BE 실제 | FE 실제 | 판정 |
| --- | --- | --- | --- | --- | --- |
| B1 | question 필드 | min 2, max 2000 | AskRequest에 검증 포함 | nl2sqlFormSchema: non-empty만 | ⚠️ FE max 미검증 |
| B2 | datasource_id | 사용자 선택 | 필수 파라미터 | `DEFAULT_DATASOURCE='ds_business_main'` 하드코딩 (Nl2SqlPage.tsx:11) | ❌ FE 하드코딩 |
| B3 | options.use_cache | bool, default true | AskOptions.use_cache=True | 기본값 사용 | ✅ |
| B4 | options.include_viz | bool, default true | AskOptions.include_viz=True | 기본값 사용 | ✅ |
| B5 | options.row_limit | int, default 1000, max 10000 | AskOptions.row_limit=1000 | 사용자 설정 UI 없음 | ⚠️ |
| B6 | options.dialect | string, default "postgres" | AskOptions.dialect="postgres" | 기본값 사용 | ✅ |
| B7 | direct-sql 엔드포인트 | Admin 전용 SQL 실행 | text2sql.py POST /direct-sql (admin 체크) | UI 없음 | ❌ FE 미구현 |
| B8 | React max_iterations | int, default 5, max 10 | ReactOptions.max_iterations=5 | 기본값 사용 | ✅ |
| B9 | React stream 플래그 | bool, default true | ReactOptions.stream=True | NDJSON 스트리밍 사용 | ✅ |

#### 5.3 응답 스키마 (C1-C15)

| ID | 갭 | 설계 문서 | BE 실제 | FE 실제 | 판정 |
| --- | --- | --- | --- | --- | --- |
| C1 | success 래퍼 | `{success, data?, error?}` | 구현됨 | response.data 직접 접근 (success 체크 없음) | ⚠️ |
| C2 | data.question 에코 | 원래 질문 반환 | 구현됨 | 로컬 상태 사용 (무시) | ✅ 동작 영향 없음 |
| C3 | data.sql | SQL 문자열 | 구현됨 | SqlPreview에서 표시 | ✅ |
| C4 | data.result | `{columns, rows, row_count}` | 구현됨 | 기본 테이블로 표시 | ✅ |
| C5 | data.visualization | `{chart_type, config}` | recommend_visualization() | ChartRecommender (bar/line/pie만) | ⚠️ scatter/kpi_card 미지원 |
| C6 | data.summary | LLM 결과 요약 | 구현됨 | **미표시** | ❌ |
| C7 | metadata.execution_time_ms | 실행 시간 | 구현됨 | 미표시 | ⚠️ |
| C8 | metadata.execution_backend | 백엔드 정보 | 구현됨 | 미표시 | ⚠️ |
| C9 | metadata.guard_status | SQL Guard 결과 | 구현됨 | 미표시 | ⚠️ |
| C10 | metadata.guard_fixes | Guard 수정 내용 | 구현됨 | 미표시 | ⚠️ |
| C11 | metadata.schema_source | 스키마 출처 | 구현됨 | 미표시 | ⚠️ |
| C12 | metadata.tables_used | 사용 테이블 목록 | 구현됨 | 미표시 | ⚠️ |
| C13 | error.code | 에러 코드 | 구현됨 (QUESTION_TOO_SHORT 등) | 코드별 처리 없음 | ⚠️ |
| C14 | error.message | 에러 메시지 | 구현됨 | generic 표시 | ✅ |
| C15 | error.details | 상세 에러 정보 | 선택적 포함 | 미표시 | ⚠️ |

#### 5.4 ReAct 스트리밍 (D1-D4)

| ID | 갭 | 설계 문서 | BE 실제 | FE 실제 | 판정 |
| --- | --- | --- | --- | --- | --- |
| D1 | NDJSON 포맷 | `application/x-ndjson` | StreamingResponse + NDJSON (text2sql.py) | postReactStream() NDJSON 파싱 | ✅ |
| D2 | Step 타입 (9개) | select/generate/validate/fix/execute/quality/triage/result/error | react_agent.py 모든 9개 구현 | callbacks 처리 (onStep/onResult/onError) | ✅ |
| D3 | Iteration 추적 | iteration 번호 포함 | 각 step에 iteration 포함 | streamLog에 누적 | ✅ |
| D4 | Progress 타임라인 | 단계별 진행 UI | 해당 없음 (FE 책임) | ThinkingIndicator만 (타임라인 없음) | ❌ 미구현 |

#### 5.5 인증/인가 (E1-E5)

| ID | 갭 | 설계 문서 | BE 실제 | FE 실제 | 판정 |
| --- | --- | --- | --- | --- | --- |
| E1 | JWT Bearer | `Authorization: Bearer {token}` | HTTPBearer + jwt.decode (auth.py) | oracleApi 토큰 헤더 포함 | ✅ |
| E2 | Role-based Access | admin/manager/attorney/analyst/engineer | requires_role() (auth.py) | RoleGuard 존재하나 nl2sql 라우트 미적용 (routeConfig.tsx:80) | ❌ |
| E3 | Tenant Isolation | X-Tenant-Id 헤더 | CurrentUser.tenant_id 사용 | API 클라이언트 자동 주입 여부 미확인 | ⚠️ |
| E4 | Rate Limiting 핸들링 | 429 에러 처리 | rate_limit 의존성 구현 | 429 에러 핸들링 없음 | ⚠️ |
| E5 | Admin-only 기능 | /direct-sql, PUT description | admin 체크 구현됨 | admin UI 없음 | ⚠️ |

#### 5.6 차트 추천 (F1-F7)

| ID | 갭 | 설계 문서 | BE 실제 | FE 실제 | 판정 |
| --- | --- | --- | --- | --- | --- |
| F1 | Chart Type 추론 | 데이터 패턴 기반 | _infer_column_role() + 규칙 기반 (visualize.py) | ChartRecommender 렌더링 | ✅ |
| F2 | Config: x/y columns | x_column, y_column | bar/line에서 사용 | 처리됨 | ✅ |
| F3 | Pie: label/value | label_column, value_column | pie에서 label_column/value_column | **x_column으로 접근 (키 불일치)** | ❌ |
| F4 | KPI Card | value_column, label | kpi_card 반환 | **렌더링 없음** | ❌ |
| F5 | Scatter chart | x_column, y_column | 타입만 존재 (추천 로직 없음) | 타입만 존재 (렌더링 없음) | ❌ BE/FE 모두 |
| F6 | Table fallback | 차트 불가 시 | else 분기에서 table 반환 | data 시 기본 표 표시 | ✅ |
| F7 | Auto-recommendation | time→line, category→bar 등 | visualize.py 규칙 구현 | BE 결과 수신하여 렌더링 | ✅ |

#### 5.7 프론트엔드 전용 (G1-G15)

| ID | 갭 | 설계 문서 | FE 실제 | 재사용 컴포넌트 | 판정 |
| --- | --- | --- | --- | --- | --- |
| G1 | DatasourceSelector | 데이터소스 선택 드롭다운 | 없음 (하드코딩) | Select (Shadcn), SchemaExplorer | ❌ |
| G2 | Mode Toggle | ask/react 전환 | mode state 구현 (Nl2SqlPage.tsx) | — | ✅ |
| G3 | Empty State | 초기 안내 화면 | 기본 UI만 | EmptyState | ⚠️ |
| G4 | MessageBubble | 대화형 말풍선 | MessageBubble 존재 (33 lines) | MessageBubble | ✅ |
| G5 | SqlPreview | SQL 미리보기+복사 | SqlPreview 존재 (36 lines) | SqlPreview | ✅ |
| G6 | ThinkingIndicator | 로딩 표시 | 존재 (10 lines, 단순) | ThinkingIndicator | ✅ |
| G7 | SQL Editor (Monaco) | SQL 수정 가능 에디터 | 의존성 있으나 NL2SQL 미사용 | MonacoEditor | ❌ |
| G8 | Copy to Clipboard | SQL/결과 복사 | SqlPreview에 copy 버튼 | — | ✅ |
| G9 | Export Results | CSV/Excel 내보내기 | 없음 | — | ❌ |
| G10 | Streaming Progress | ReAct 진행률 표시 | streamLog 누적만 (진행 바 없음) | SyncProgress 참조 | ⚠️ |
| G11 | Chart Tab Switching | 차트/테이블/SQL 탭 | 없음 (순차 표시) | ChartSwitcher | ❌ |
| G12 | Error Boundary | 컴포넌트 에러 포착 | 없음 | ErrorState | ❌ |
| G13 | Network Error Retry | 네트워크 에러 재시도 | 없음 | ErrorState, toast | ❌ |
| G14 | Multi-turn Context | 대화 맥락 유지 | messages 표시만 (API 미전달) | — | ❌ |
| G15 | Result Table | 구조화된 결과 테이블 | 기본 div 표시 (DataTable 미사용) | DataTable | ⚠️ |

#### 5.8 백엔드 전용 (H1-H10)

| ID | 갭 | 설계 문서 | BE 실제 | 판정 |
| --- | --- | --- | --- | --- |
| H1 | direct-sql | Admin raw SQL 실행 | text2sql.py POST /direct-sql | ✅ |
| H2 | Query History | 질의 이력 저장 | query_history_repo 저장 | ✅ |
| H3 | SQL Guard | SQL 보안 검증 | sql_guard.validate() | ✅ |
| H4 | Datasource Registry | /meta/datasources | meta.py GET /datasources | ✅ |
| H5 | Table Description Update | PUT /tables/{name}/description | meta.py 구현됨 | ✅ |
| H6 | Column Description Update | PUT /columns/{fqn}/description | meta.py 구현됨 | ✅ |
| H7 | Cache Postprocessor | 성공 쿼리 캐시 반영 | cache_postprocess.py | ✅ |
| H8 | LLM Factory | LLM 제공자 추상화 | llm_factory | ✅ |
| H9 | Embedding Generation | 질문 벡터화 | nl2sql_pipeline.py (선택적) | ✅ |
| H10 | Quality Scoring | LLM 기반 품질 점수 | react_agent.py run_step_quality() | ✅ |

### 6. NL2SQL 단계별 구현 요약

> 상세 구현 계획은 별도 문서 참조: [04d-phase-nl2sql.md](04d-phase-nl2sql.md)

| Phase | 범위 | 해결 항목 | 우선순위 |
| --- | --- | --- | --- |
| Phase 1 | 긴급 수정 (런타임 버그·보안) | F3, F5, E2, E4 | 🔴 긴급 |
| Phase 2 | 핵심 기능 완성 | G4-G7, G10, G15, A8, B2 | 🟠 높음 |
| Phase 3 | UX 고도화 | G3, G8, G9, G11-G14, D4 | 🟡 중간 |
| Phase 4 | 고급 기능 | B7, H1, H3, H4, H7, H9 | 🟢 보통 |
| Phase 5 | 품질·문서 동기화 | A1, A4, B1, B5, E3 | 🔵 후순위 |

### 7. NL2SQL 테스트 통과 기준 요약

> 상세 Gate 기준은 별도 문서 참조: [04d-phase-nl2sql.md](04d-phase-nl2sql.md)
> 전체 Phase별 완료 기준 통합 문서: [04d-gate-pass-criteria.md](04d-gate-pass-criteria.md)

| Gate | 핵심 통과 기준 |
| --- | --- |
| Gate 1 | Pie chart config 키 정상 동작, RoleGuard 적용, 429 핸들링 |
| Gate 2 | DatasourceSelector 동작, MessageBubble 실 API 연동, Meta API 호출 |
| Gate 3 | ReAct 타임라인 UI, Chart 탭 전환, Error Boundary, CSV 내보내기 |
| Gate 4 | direct-sql admin UI, SQL Editor (Monaco), 캐시 설정 UI |
| Gate 5 | API prefix 정규화, 문서-코드 sync 검증 |

---

## Part II — 온톨로지 뷰 갭 분석

### 8. 아키텍처 의사결정

#### 8.1 기존 인프라 전수 조사 결과

**A. Backend — Synapse (Neo4j Primary Owner)**

| 구성요소 | 상태 | 파일 경로 | Lines |
| --- | --- | --- | --- |
| Neo4j 5.18 async driver | ✅ PRODUCTION | `services/synapse/app/core/neo4j_client.py` | — |
| Neo4j Bootstrap (Schema v2.0.0) | ✅ PRODUCTION | `services/synapse/app/graph/neo4j_bootstrap.py` | 97 |
| OntologyService (CRUD+BFS) | ✅ PRODUCTION | `services/synapse/app/services/ontology_service.py` | 371 |
| OntologyIngestor (Redis→Neo4j) | ✅ PRODUCTION | `services/synapse/app/graph/ontology_ingest.py` | 106 |
| MetadataGraphService | ✅ PRODUCTION | `services/synapse/app/services/metadata_graph_service.py` | 325 |
| GraphSearchService | ⚠️ 하드코딩 | `services/synapse/app/services/graph_search_service.py` | 266 |
| Ontology API (13 endpoints) | ✅ PRODUCTION | `services/synapse/app/api/ontology.py` | 132 |
| Graph API (7 endpoints) | ✅ PRODUCTION | `services/synapse/app/api/graph.py` | 100 |
| Metadata Graph API | ✅ PRODUCTION | `services/synapse/app/api/metadata_graph.py` | 141 |

**B. Backend — Oracle (NL2SQL Consumer)**

| 구성요소 | 상태 | 파일 경로 | Lines |
| --- | --- | --- | --- |
| OracleSynapseACL | ✅ PRODUCTION | `services/oracle/app/infrastructure/acl/synapse_acl.py` | 432 |
| Meta API | ⚠️ 하드코딩 폴백 | `services/oracle/app/api/meta.py` | 239 |

**C. Frontend — Canvas**

| 구성요소 | 상태 | 파일 경로 | Lines |
| --- | --- | --- | --- |
| Route `/data/ontology` | ✅ ROUTED | `canvas/src/lib/routes/routeConfig.tsx:81` | — |
| OntologyBrowser | ❌ STUB (3 mock 노드) | `canvas/src/pages/ontology/OntologyBrowser.tsx` | 68 |
| OntologyPage | ❌ DEAD CODE (완성됨) | `canvas/src/pages/ontology/OntologyPage.tsx` | 78 |
| GraphViewer (ForceGraph2D) | ✅ COMPLETE (mock) | `canvas/src/pages/ontology/components/GraphViewer.tsx` | 164 |
| NodeDetail | ✅ COMPLETE (mock) | `canvas/src/pages/ontology/components/NodeDetail.tsx` | 129 |
| SearchPanel | ✅ COMPLETE (mock) | `canvas/src/pages/ontology/components/SearchPanel.tsx` | 30 |
| LayerFilter | ✅ COMPLETE (mock) | `canvas/src/pages/ontology/components/LayerFilter.tsx` | 36 |
| PathHighlighter | ✅ COMPLETE (mock) | `canvas/src/pages/ontology/components/PathHighlighter.tsx` | — |
| Types (4계층) | ✅ COMPLETE | `canvas/src/features/ontology/types/ontology.ts` | 36 |
| useOntologyMock | ❌ MOCK ONLY | `canvas/src/features/ontology/hooks/useOntologyMock.ts` | 144 |
| useOntologyStore (Zustand) | ✅ COMPLETE | `canvas/src/features/ontology/store/useOntologyStore.ts` | 62 |
| synapseApi client | ✅ EXISTS | `canvas/src/lib/api/clients.ts:21` (ontology 함수 없음) | — |

**GraphSearchService 하드코딩 상세** (`graph_search_service.py`):

```python
# __init__() lines 9-60 — 전체 인메모리 하드코딩
self._tables = {
    "cases":         {"columns": ["id(uuid,PK)", "name(text)"]},
    "processes":     {"columns": ["id(uuid,PK)", "case_id(FK)", "org_id(FK)", "efficiency_rate(numeric)"]},
    "organizations": {"columns": ["id(uuid,PK)", "name(text)"]},
    "metrics":       {"columns": ["id(uuid,PK)", "case_id(FK)", "value(numeric)"]},
}
self._fk_edges = [
    ("processes", "cases",         {"from_column": "case_id", "to_column": "id"}),
    ("processes", "organizations", {"from_column": "org_id",  "to_column": "id"}),
    ("metrics",   "cases",         {"from_column": "case_id", "to_column": "id"}),
]
```

이 하드코딩은 NL2SQL의 스키마 탐색 전체를 4개 테이블로 제한하며, 실제 Neo4j에 수십 개 테이블/컬럼이 존재함에도 활용하지 못하는 **치명적 병목**이다.

#### 8.2 사용자 제안 아키텍처 vs 기존 아키텍처 비교

| 기술 스택 | 사용자 제안 | 기존 구현 | 판정 | 근거 |
| --- | --- | --- | --- | --- |
| Neo4j | Primary | Neo4j 5.18 운영 중 | **유지** | 이미 프로덕션 |
| n10s (neosemantics) | Primary (RDF import) | 미사용 | **불채택** | RDF 파일 없음. native property graph 사용. 도입 시 복잡성만 증가 |
| neomodel (Python OGM) | Primary (OGM) | neo4j==5.18.0 async driver | **불채택** | neomodel은 sync-only. 기존 전체가 async 패턴. 전환 시 아키텍처 훼손 |
| rdflib | Secondary (검증) | 미사용 | **불채택** (export용 한정) | RDF 아티팩트 없음. Phase O5에서 export-only 모듈로 한정 도입 가능 |
| Owlready2 | Optional (추론) | 미사용 | **불채택** | OWL 파일 없음. 추론 필요 시 Cypher BFS로 충분 (`path_to()` 이미 구현) |

#### 8.3 채택 판정 요약

```
[결정] 기존 async neo4j driver + raw Cypher 아키텍처 유지
       → 기술 도입을 위한 도입을 하지 않는 아키텍처적 절제

[진짜 갭]
  1. FE-BE 연동 단절 (OntologyPage dead code)
  2. Concept-Schema 매핑 부재 (GlossaryTerm↔Table 관계 없음)
  3. NL2SQL 메타 하드코딩 (GraphSearchService 4개 테이블 고정)
  4. GlossaryTerm-Ontology 브릿지 부재
  5. Impact Analysis 뷰 부재
```

### 9. 온톨로지 뷰 갭 분석 상세 (20개 항목, I1-I20)

#### 9.1 FE-BE 연동 (I1-I5)

| ID | 갭 | 판정 | 핵심 |
| --- | --- | --- | --- |
| I1 | OntologyPage 미라우팅 | **CRITICAL** | `routeConfig.tsx:81` → OntologyBrowser(stub). 완성된 OntologyPage(78 lines, ForceGraph2D)는 dead code |
| I2 | FE API 클라이언트 부재 | **CRITICAL** | `synapseApi` 인스턴스 존재하나 ontology 함수 0개. `useOntologyMock`이 14개 하드코딩 노드 반환 |
| I3 | BE→FE 데이터 변환 레이어 부재 | **HIGH** | BE: `{nodes[].layer, relations[].source_id}` vs FE: `OntologyNode.label, OntologyEdge.source` — 타입 불일치 |
| I4 | case_id 컨텍스트 전달 누락 | **HIGH** | BE OntologyService 모든 메서드가 case_id 필수. FE OntologyPage에 case_id 개념 없음 |
| I5 | 실시간 업데이트 미반영 | **MEDIUM** | WebSocket/SSE push 없음. Phase O1에서 polling, Phase O4에서 SSE |

#### 9.2 Concept-Schema 매핑 뷰 (I6-I8)

| ID | 갭 | 판정 | 핵심 |
| --- | --- | --- | --- |
| I6 | GlossaryTerm↔Table/Column 매핑 뷰 부재 | **CRITICAL** | GlossaryTerm 노드와 Table/Column 노드 모두 Neo4j에 존재하지만 **관계(edge) 없음** |
| I7 | 4계층 노드↔Schema 엔티티 연결 부재 | **HIGH** | Ontology(case_id 기반)와 Schema(tenant_id+datasource 기반)가 별도 그래프 영역 |
| I8 | 태그 기반 매핑 시스템 활용도 저조 | **MEDIUM** | `MetadataGraphService.add_entity_tag()` 완전 작동. FE 태그 UI 없음 |

#### 9.3 영향 분석 뷰 (I9-I10)

| ID | 갭 | 판정 | 핵심 |
| --- | --- | --- | --- |
| I9 | Impact Analysis 뷰 부재 | **HIGH** | cross-domain(Schema→Ontology) BFS 없음. PathHighlighter는 Ontology 내부만 |
| I10 | 변경 이력 추적 부재 | **LOW** | updated_at만 기록. 이전 값 없음 (`ontology-model.md` 명시) |

#### 9.4 NL2SQL 메타 통합 (I11-I14) — 핵심 섹션

| ID | 갭 | 판정 | 핵심 |
| --- | --- | --- | --- |
| I11 | Oracle Meta API 하드코딩 폴백 | **MEDIUM** | `meta.py:28-44`의 `_fallback_tables()`가 "processes"/"organizations" 하드코딩 |
| I12 | GraphSearchService 인메모리 하드코딩 | **HIGH** | `graph_search_service.py:9-60`에서 4개 테이블 + 3개 FK 하드코딩. **실제 Neo4j 미사용** |
| I13 | NL2SQL Pipeline의 Ontology 컨텍스트 미활용 | **HIGH** | "매출 추이" → Revenue:Measure → revenue 테이블 연결 불가. 개념→물리 매핑 자동화 부재 |
| I14 | datasource registry가 환경변수 JSON 기반 | **MEDIUM** | `ORACLE_DATASOURCES_JSON`에서 파싱. Synapse DataSource 노드 미활용 |

이 섹션(I11-I14)이 **전체 시스템의 인지 엔진 핵심**이다. 이 갭이 해결되면:
- "매출 추이" → `Revenue:Measure` → `revenue.amount` (자동 매핑)
- "고객 이탈" → `churn_rate:KPI` → `customer.status = 'churned'` (자동 매핑)
- "신규 조직 증가" → `onboarding:Process` → `organization.created_at` (자동 매핑)

#### 9.5 GlossaryTerm ↔ Ontology 브릿지 (I15-I16)

| ID | 갭 | 판정 | 핵심 |
| --- | --- | --- | --- |
| I15 | GlossaryTerm과 Ontology 노드 분리 | **HIGH** | GlossaryTerm(tenant_id)과 Ontology(case_id) 간 관계 없음 |
| I16 | Fulltext index FE 미활용 | **MEDIUM** | `neo4j_bootstrap.py`에서 `ontology_fulltext` + `schema_fulltext` 생성됨. FE SearchPanel은 클라이언트사이드 필터만 |

#### 9.6 데이터 품질/거버넌스 (I17-I20)

| ID | 갭 | 판정 | 핵심 |
| --- | --- | --- | --- |
| I17 | HITL 리뷰 UI 부재 | **MEDIUM** | `ontology-model.md`에 HITL 생명주기 정의됨. hitl_review_queue 스키마 문서만 존재 |
| I18 | 데이터 품질 대시보드 부재 | **LOW** | 품질 기준 + Cypher 쿼리 문서화됨. 서비스 레이어 미구현 |
| I19 | OWL/RDF export 미지원 | **LOW** | interoperability용. rdflib export-only 모듈로 한정 도입 |
| I20 | 온톨로지 버전 관리 부재 | **LOW** | MetadataSnapshot 있으나 ontology graph 스냅샷 없음 |

### 10. 4대 리스크 분석 및 완화 전략

#### 리스크 1: GraphSearchService 전면 재작성 (O3-1)

- **위험**: 하드코딩→Neo4j Cypher 전환 시 기존 의존 모듈 파손, 검색 성능 저하, fulltext 미튜닝 병목
- **영향 범위**: `graph.py` 7개 엔드포인트, `synapse_acl.py` search_schema_context(), `nl2sql_pipeline.py` _search_and_catalog()
- **완화 전략**: `search()` 제거하지 않고 **`search_v2()` 병행 운영**
  - 기존 `search()` → deprecated 마킹, 로그에 `legacy_search=true` 태그
  - `search_v2()` → Neo4j Cypher 기반
  - 전환 판정 기준: v2 응답 시간 < v1 x 1.5 AND 정확도 >= v1
  - 전환 완료 후 `search()` 제거 (O3 Gate 통과 후)

#### 리스크 2: case_id vs tenant_id 그래프 도메인 분리 (O2-O3 교차)

- **위험**: Ontology(case_id 기반)와 Schema(tenant_id+datasource 기반)가 별도 그래프 영역 → 단순 JOIN 불가
- **완화 전략**: 3-hop 브릿지 관계 모델

```cypher
(g:GlossaryTerm {tenant_id: $tid})
  -[:DEFINES]->
(o:Resource|Process|Measure|KPI {case_id: $cid})
  -[:MAPS_TO]->
(t:Table {tenant_id: $tid, datasource: $ds})
```

- Phase O2에서 `MAPS_TO` 관계 + 인덱스 구현
- Phase O3에서 NL2SQL pipeline이 이 경로를 Cypher로 탐색
- case_id↔tenant_id 매핑은 Case 노드의 tenant_id 속성으로 해결 (이미 존재)

#### 리스크 3: ConceptMapView UI 복잡도 (O2-4)

- **위험**: 좌측 GlossaryTerm + 우측 Table 트리 + 연결선 = mini data lineage tool 수준 난이도
- **완화 전략**: 2단계 점진적 구현
  - **O2 Phase A** (1차): CRUD 리스트 UI — GlossaryTerm 목록, Table 드롭다운, 매핑 생성/삭제 버튼
  - **O2 Phase B** (2차, O4와 병합): 시각 연결선 UI — ForceGraph2D bipartite layout
  - O2 Gate는 Phase A 기준으로 판정

#### 리스크 4: Impact Analysis 범위 폭발 (O4-1)

- **위험**: cross-domain BFS (Table→Measure→KPI→CachedQuery) depth 무제한 시 그래프 폭발
- **완화 전략**: 강제 제한
  - `depth` 파라미터 필수: **default=3, hard cap=5**
  - Cypher에 `*..{depth}` 범위 제한 강제
  - 응답 노드 수 hard limit: **100개** (초과 시 truncated + warning)
  - FE depth selector: 1~5 슬라이더 (default 3)

### 11. 온톨로지 뷰 단계별 구현 요약

> 상세 구현 계획은 별도 문서 참조

| Phase | 범위 | 해결 항목 | 상세 문서 |
| --- | --- | --- | --- |
| O1 | FE-BE 연동 | I1-I5 | [04d-phase-ontology-O1-O2.md](04d-phase-ontology-O1-O2.md) |
| O2 | Concept-Schema 매핑 | I6-I8 | [04d-phase-ontology-O1-O2.md](04d-phase-ontology-O1-O2.md) |
| O3 | **NL2SQL 인지 엔진 통합** | I11-I14 | [04d-phase-ontology-O3.md](04d-phase-ontology-O3.md) |
| O4 | Impact Analysis | I9-I10 | [04d-phase-ontology-O4-O5.md](04d-phase-ontology-O4-O5.md) |
| O5 | 고급 기능 | I15-I20 | [04d-phase-ontology-O4-O5.md](04d-phase-ontology-O4-O5.md) |

### 12. 온톨로지 뷰 테스트 통과 기준

> 전체 Phase별 완료 기준 통합 문서: [04d-gate-pass-criteria.md](04d-gate-pass-criteria.md)

**Gate O1 (FE-BE 연동)** — PASS (2026-02-24)

- [x] `/data/ontology` 접속 시 ForceGraph2D 렌더링 (3 mock 노드가 아닌 실제 그래프)
- [x] `ontologyApi.getCaseOntology(caseId)` 호출 시 Synapse API 200 응답
- [x] LayerFilter "Process" 해제 시 Process 노드 그래프에서 제거
- [x] 2 노드 클릭 → BE `path-to` API 호출 → 경로 하이라이트
- [x] Synapse 503 시 에러 메시지 표시 (빈 화면 아님)
- [x] 빈 ontology 시 "데이터가 없습니다" EmptyState 표시

**Gate O2 (Concept-Schema 매핑)** — PASS (2026-02-24)

- [x] `POST /concept-mappings` 후 Neo4j에 `MAPS_TO` 관계 존재 확인
- [x] 특정 Table에 매핑된 GlossaryTerm 역조회 정확
- [x] "매출" 검색 시 "revenue" 테이블 자동 후보 제안 (fulltext 기반)
- [x] ConceptMapView: GlossaryTerm 목록 + Table 드롭다운 렌더링 (Phase A)

**Gate O3 (NL2SQL 인지 엔진) — 핵심** — CONDITIONAL PASS (2026-02-24)

- [x] `search_v2()`가 Neo4j Cypher 실행 확인 (하드코딩 아님)
- [x] `search()` ↔ `search_v2()` A/B 비교 로그 존재
- [x] NL2SQL system prompt에 비즈니스 용어 매핑 포함
- [x] "매출 추이" → revenue 테이블 SELECT 생성 (e2e)
- [x] "고객 이탈률" → customer 테이블 + status 필터 (e2e)
- [x] Synapse 장애 시 Oracle graceful degradation (503 반환, crash 없음)
- [x] `_fallback_tables()` 코드에서 완전 제거됨

**Gate O4 (Impact Analysis)** — PASS (2026-02-25)

- [x] Table 변경 → 연결된 Measure/KPI 목록 반환 (depth=3)
- [x] KPI 선택 → 의존하는 Measure→Process→Resource 역추적
- [x] ImpactAnalysisPanel UI: 영향 노드 목록 + 경로 하이라이트
- [x] depth=6 요청 시 hard cap 5로 제한됨

**Gate O5 (고급 기능)** — PASS (2026-02-25)

- [x] `GET /export?format=turtle` → valid Turtle RDF 반환
- [x] 품질 리포트: orphan_count, low_confidence_count 반환
- [x] HITL Approve → verified=true 업데이트. Reject → 노드 삭제
- [x] 2개 스냅샷 diff에 추가/삭제 노드 포함

---

## Part III — 통합 전략

### 13. Phase 간 의존성 맵

```
NL2SQL Phase 2 (A8 meta API 연동)      ←→  Ontology Phase O3 (NL2SQL 메타 통합)
NL2SQL Phase 4 (H4 /meta/datasources)  ←→  Ontology Phase O2 (Concept-Schema 매핑)
NL2SQL Phase 4 (H1 direct-sql)         ←→  Ontology Phase O4 (Impact Analysis — cached query 영향)
NL2SQL Phase 5 (문서 동기화)            ←→  Ontology Phase O5 (통합 문서 정리)
```

### 14. 최적화된 실행 순서

O3(NL2SQL 인지 엔진)이 전체 시스템의 질을 결정하므로, NL2SQL P2~P3(핵심 기능+UX)가 **O3 위에 구축**되어야 진정한 가치를 발휘한다. O3 없이 NL2SQL P2를 먼저 하면 여전히 하드코딩 기반으로 구축하게 되어 이후 재작업이 필요하다.

```
1. NL2SQL Phase 1 (긴급 버그·보안 안정화)
2. Ontology Phase O1 (FE-BE 연동 — 독립 실행)
3. Ontology Phase O2-A (Concept-Schema 매핑 최소 버전 — CRUD 리스트)
4. 🔴 Ontology Phase O3 (NL2SQL 인지 엔진 통합 — 핵심)
5. NL2SQL Phase 2~3 (핵심 기능 + UX — O3 위에 구축)
6. Ontology Phase O2-B + O4 (시각 UI + Impact Analysis — 병렬)
7. NL2SQL Phase 4 + Ontology Phase O4 나머지 (병렬)
8. NL2SQL Phase 5 + Ontology Phase O5 (병렬)
```

### 15. 시스템 완성 시 파급 효과

| 지표 | 현재 (Layer 0) | O3 완성 후 (Layer 2) | 근거 |
| --- | --- | --- | --- |
| SQL 정확도 | 테이블명 직접 매칭만 | 의미 기반 매핑 → 동의어/비즈니스 용어 지원 | "매출" → revenue.amount 자동 |
| Hallucination | 존재하지 않는 테이블 참조 가능 | 그래프에 없는 테이블 차단 | Neo4j 검증 |
| 도메인 적합성 | 범용 SQL | 업종별 온톨로지 반영 | KPI/Measure 관계 활용 |
| BI 수준 분석 | 단일 테이블 쿼리 중심 | 다중 테이블 JOIN 경로 자동 발견 | FK graph traversal |
| 검색 범위 | 4개 하드코딩 테이블 | Neo4j 전체 스키마 그래프 | fulltext + vector search |

### 16. 변경 이력

| 일자 | 내용 | 비고 |
| --- | --- | --- |
| 2026-02-24 | 초안 작성 — NL2SQL 73개 + 온톨로지 20개 갭 분석 | 사용자 피드백 8개 항목 반영 |
| 2026-02-25 | 전체 Gate 판정 기록 + 현황 요약 업데이트 (97% 해결) | Docker E2E 14/14 PASS, 문서 현행화 잔여 |
