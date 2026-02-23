# Canvas Full 스펙 구현 계획 (미구현·스텁·문서 갭)

> **근거**: [docs/future-implementation-backlog.md](../../future-implementation-backlog.md), [docs/frontend-design-gap-analysis.md](../../frontend-design-gap-analysis.md), **코드 검증**: `apps/canvas/src/` 실제 구현 대조  
> **범위**: 설계 문서(`apps/canvas/docs/04_frontend/`) 대비 미구현·스텁·Mock·문서 불일치 항목. Core 풀스펙 계획서와 동일한 구조로 단계별 구현 계획을 수립한다.  
> **작성일**: 2026-02-23  
> **구현 상태 (코드 기준 2026-02 검증)**: **Phase A–G 완료.** 갭: Admin 전용 설정·설정 로그/AI 분석, 데이터소스 extract-metadata SSE, Watch 규칙 CRUD·문서 동기화(routing/directory-structure).

---

## 1. 목적

- Canvas의 **미구현**, **스텁/Mock**, **설계 문서와 불일치**인 항목을 `apps/canvas/docs/04_frontend/` 설계 문서에 맞춰 Full 스펙으로 구현하기 위한 계획.
- Phase별 설계 문서 참조, 티켓, 선행 조건, 통과 기준을 명시. **갭은 코드 기준으로 검증한 결과를 반영.**

---

## 2. 참조 설계 문서

| 문서 | 용도 |
|------|------|
| **04_frontend/case-dashboard.md** | 케이스 대시보드, StatsCard, CaseFilters, CaseTable, CaseTimeline, 역할별 패널(ApprovalQueue, MyWorkitems), QuickActions, RoleGreeting |
| **04_frontend/document-management.md** | DocumentReviewPage, ReviewPanel, DocumentDiffViewer, 케이스 중첩 경로, 리뷰 API |
| **04_frontend/process-designer.md** | ProcessCanvas(react-konva), PropertyPanel, Minimap, Yjs 협업, ConformanceOverlay, VariantList |
| **04_frontend/watch-alerts.md** | AlertFeed, AlertRuleEditor, EventTimeline, NotificationBell, SSE/WS, 알림 유형·규칙·생명주기 |
| **04_frontend/datasource-manager.md** | 데이터소스 목록·연결 폼, **SSE 기반 동기화 진행률**, 스키마 탐색기 |
| **04_frontend/admin-dashboard.md** | 설정 라우트 구조, **admin 전용** 사이드바·RoleGuard, SystemMonitor/LogExplorer/UserManagement/SystemConfig, 로그 탭(explorer·AI 분석 챗봇) |
| **04_frontend/design-system.md** | Design Tokens, 다크 모드 |
| **04_frontend/routing.md** | 라우트 맵, 인증/보호, 코드 분할 |
| **04_frontend/directory-structure.md** | features/ 하위 디렉토리·api·hooks·components 규칙 |
| **04_frontend/implementation-guide.md** | 에러 처리, 폼(RHF+Zod), i18n, 실시간 통신 |
| **04_frontend/event-streams.md** | watchStream(SSE), streamManager(POST 스트림), WebSocket 미사용 |
| **04_frontend/nl2sql-chat.md** | 대화형 쿼리, SSE 스트리밍, SQL/결과/차트 추천 |
| **04_frontend/olap-pivot.md** | OLAP 피벗, DnD, 드릴다운, ChartSwitcher |
| **04_frontend/ontology-browser.md** | 4계층 필터, GraphViewer, NodeDetail, 테이블 뷰 |
| **04_frontend/what-if-builder.md** | What-if 시나리오, 매개변수 슬라이더, Vision API |
| **02_api/api-contracts.md** | Core/Vision/Oracle/Synapse/Weaver API 계약 |

---

## 3. 갭 요약 (코드 기준)

아래는 `apps/canvas/src/` 실제 코드와 `apps/canvas/docs/04_frontend/` 설계 문서를 대조한 결과이다.

| 영역 | 현재 상태 (코드) | Full 스펙 (설계 문서) |
|------|------------------|------------------------|
| **케이스 목록/통계/타임라인** | **구현됨**: useCases→casesApi, useCaseActivities→listCaseActivities, MOCK 제거. | case-dashboard.md: API 기반 목록·통계·타임라인 |
| **ApprovalQueuePanel·MyWorkitemsPanel** | **구현됨**: useApprovalQueue, useMyWorkitems, useApproveHitl, useReworkWorkitem 연동. | case-dashboard.md: SUBMITTED·할당 워크아이템 실데이터 |
| **Process Designer** | **구현됨**: PropertyPanel, Minimap. Yjs·ConformanceOverlay·VariantList 스텁(연동 예정). | process-designer.md: 미니맵·속성 패널·Yjs·마이닝(선택) |
| **문서 리뷰** | **구현됨**: documentReviewApi→coreApi POST .../review, ReviewPanel, DocumentDiffViewer. | document-management.md: 리뷰 API 연동 |
| **Design Tokens·다크 모드·i18n·Data Router** | **구현됨**: tokens.css, themeStore, ThemeToggle, react-i18next, routeConfig(createBrowserRouter). | design-system.md, implementation-guide.md, routing.md |
| **설정(Admin)** | **갭**: Sidebar에 설정이 모든 사용자에게 노출. RoleGuard(admin) 미적용. admin-dashboard.md: "관리 (Admin Only)"·설정 하위 admin 전용. | admin-dashboard.md §1.2: admin만 설정 메뉴 표시, RoleGuard(roles=['admin']) |
| **설정 > 로그** | **갭**: SettingsLogsPage "추후 연동" 스텁. 설계: LogExplorerPage, 탭(explorer·AI 분석 챗봇). | admin-dashboard.md §3: 로그 탐색·AI 분석 챗봇 탭 |
| **데이터소스 동기화** | **갭**: SyncProgress는 legacy POST /datasource/{id}/sync + listJobs. **extract-metadata SSE** 미호출. 설계: SSE 진행률(phase·percent)·테이블별 진행. | datasource-manager.md §3: SSE 기반 동기화 진행률 표시 |
| **Watch 알림** | **구현됨**: useAlerts, subscribeWatchStream(SSE), AlertFeed, EventTimeline, AlertRuleEditor, NotificationBell. VITE_USE_MOCK_DATA 시 Mock. **갭**: 규칙 CRUD가 Core API와 완전 연동 여부·문서 정리. | watch-alerts.md: SSE, 알림 유형·규칙·벨 |
| **NL2SQL·OLAP·온톨로지·What-if** | **구현됨**: Nl2SqlPage(oracleNl2sqlApi, 스트리밍), OlapPivotPage(visionOlapApi), OntologyBrowser(GraphViewer 등), WhatIfPage(ScenarioPanel, visionWhatIfApi). **갭**: nl2sql ChartRecommender·OLAP Mock 제거 여부·온톨로지 테이블 뷰 "구현 예정". | nl2sql-chat.md, olap-pivot.md, ontology-browser.md, what-if-builder.md |
| **라우팅 문서** | **갭**: routing.md에 "BrowserRouter + Routes"·"createBrowserRouter 미사용" 기재. 실제는 createBrowserRouter(routeConfig.tsx). | routing.md §2: 현재 구현과 일치하도록 수정 |
| **디렉토리 구조 문서** | **갭**: directory-structure.md는 features/case-dashboard/api/caseApi.ts 등. 실제는 lib/api/casesApi.ts·일부 feature만 api/ 보유. | directory-structure.md: 실제 구조 반영 |

---

## 4. Phase 개요

| Phase | 목표 | 설계 문서 | 선행 | 상태 |
|-------|------|-----------|------|------|
| **A** | 케이스 API 연동 (목록·통계·타임라인·워크아이템) | case-dashboard.md, api-contracts.md | Core cases/activities API | 완료 |
| **B** | ApprovalQueuePanel·MyWorkitemsPanel 실데이터 | case-dashboard.md, processApi | Phase A | 완료 |
| **C** | Process Designer 고도화 (PropertyPanel, Minimap, Yjs, 마이닝) | process-designer.md | Process/Synapse API | 완료 |
| **D** | 문서 리뷰 API 계약 및 연동 | document-management.md, 02_api | Core 문서 리뷰 엔드포인트 | 완료 |
| **E** | Design Tokens·다크 모드 전역 | design-system.md | - | 완료 |
| **F** | i18n 도입 | implementation-guide.md | - | 완료 |
| **G** | Data Router 전환 | routing.md | - | 완료 |
| **H** | Admin 전용 설정·설정 로그/AI 분석 | admin-dashboard.md | Core 로그/규칙 API(선택) | 미완료 |
| **I** | 데이터소스 extract-metadata SSE 연동 | datasource-manager.md, Weaver metadata-api | Weaver POST extract-metadata | 미완료 |
| **J** | Watch 규칙 CRUD·문서 정리 | watch-alerts.md, 02_api | Core Watch 규칙 API | 미완료 |
| **K** | 문서 동기화 (routing, directory-structure) | routing.md, directory-structure.md | - | 미완료 |

---

## 5. Phase A: 케이스 API 연동 (목록·통계·타임라인)

**목표**: useCases를 Mock이 아닌 Core/Gateway cases API 호출로 전환. CaseTimeline을 활동/이벤트 API로 연동.

### 5.1 참조 설계

- **case-dashboard.md**: 케이스 목록·통계는 API에서 조회, 최근 활동 타임라인은 서버 이벤트 기반.
- **02_api/api-contracts.md**: Core·Gateway cases/activities 엔드포인트 계약.

### 5.2 통과 기준 (Gate A)

- 대시보드 케이스 목록·통계가 API 응답으로 표시된다. CaseTimeline이 서버 기반 활동 데이터를 표시한다.

**구현 상태**: A1–A4 완료. lib/api/casesApi.ts, useCases, useCaseActivities, CaseTimeline API 주입.

---

## 6. Phase B: ApprovalQueuePanel·MyWorkitemsPanel 실데이터

**목표**: ApprovalQueuePanel을 Process API SUBMITTED 워크아이템과 연동. MyWorkitemsPanel을 Process "내 할당" 워크아이템과 연동.

### 6.1 참조 설계

- **case-dashboard.md** §4.4: MyWorkitemsPanel, ApprovalQueuePanel.
- **processApi.ts**: getProcessWorkitems, approveHitl, rework. 목록용 엔드포인트 Core 연동.

### 6.2 통과 기준 (Gate B)

- ApprovalQueuePanel에 실제 SUBMITTED 워크아이템 표시, 승인/반려가 Process API와 연동. MyWorkitemsPanel에 할당 워크아이템 표시.

**구현 상태**: B1–B4 완료. useApprovalQueue, useMyWorkitems, useApproveHitl, useReworkWorkitem.

---

## 7. Phase C: Process Designer 고도화 (PropertyPanel, Minimap, Yjs, 마이닝)

**목표**: PropertyPanel(우측), Minimap, Yjs 실시간 협업, ConformanceOverlay·VariantList(선택).

### 7.1 참조 설계

- **process-designer.md**: 툴박스·캔버스(react-konva), 속성 패널, 미니맵, Yjs, 프로세스 마이닝 오버레이, VariantList.

### 7.2 통과 기준 (Gate C)

- 노드 선택 시 PropertyPanel에 속성 표시·편집. Minimap이 캔버스와 연동. (선택) Yjs·마이닝.

**구현 상태**: C1–C2 완료. C3(Yjs)·C4(ConformanceOverlay, VariantList) 스텁 유지(연동 예정).

---

## 8. Phase D: 문서 리뷰 API 계약 및 연동

**목표**: DocumentReviewPage·documentReviewApi가 Core/Gateway 문서 리뷰 엔드포인트와 계약 일치.

### 8.1 참조 설계

- **document-management.md**: 리뷰 전용 페이지, 승인/반려 워크플로우.
- **documentReviewApi.ts**: POST /api/v1/cases/:caseId/documents/:docId/review (coreApi).

### 8.2 통과 기준 (Gate D)

- 문서 리뷰 액션이 설계된 API로 호출되며, 백엔드와 계약이 일치한다.

**구현 상태**: D1–D3 완료. Core 스텁 추가·coreApi 연동 검증.

---

## 9. Phase E: Design Tokens·다크 모드 전역

**목표**: design-system.md에 따른 Design Tokens 및 전역 다크 모드.

**구현 상태**: tokens.css, themeStore(persist), ThemeProvider, ThemeToggle, darkMode 'class' 완료.

---

## 10. Phase F: i18n 도입

**목표**: react-i18next, ko/en 리소스, 문자열 외부화.

**구현 상태**: lib/i18n, ko.json/en.json, LocaleToggle, useTranslation 적용 완료.

---

## 11. Phase G: Data Router 전환

**목표**: createBrowserRouter 전환, 기존 라우트·인증·레이아웃 유지.

**구현 상태**: lib/routes/routeConfig.tsx(createBrowserRouter), App.tsx→RouterProvider 완료. **문서**: routing.md는 아직 BrowserRouter 기재(Phase K에서 동기화).

---

## 12. Phase H: Admin 전용 설정·설정 로그/AI 분석

**목표**: admin-dashboard.md에 따른 설정 메뉴 admin 전용 제한, 로그 탐색·AI 분석 챗봇 탭 구현 또는 스텁 정리.

### 12.1 참조 설계

- **admin-dashboard.md** §1.1–1.3: /settings 하위 system, logs, users, config. "관리 (Admin Only)" 섹션, RoleGuard(roles=['admin']).
- **admin-dashboard.md** §3: LogExplorerPage, 탭(explorer·ai-analysis), AI 분석 챗봇 UI.

### 12.2 선행 조건

- (선택) Core 또는 Gateway 로그 조회·AI 분석 API 확정 시 실연동. 없으면 "연동 예정" 문서화 유지.

### 12.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| H1 | 설정 라우트 RoleGuard(admin) | settings 하위 라우트를 RoleGuard(roles=['admin'])로 감싸거나, Sidebar에서 admin일 때만 설정 링크 표시. | routeConfig.tsx 또는 Sidebar.tsx |
| H2 | 설정 > 로그 탭 구조 | SettingsLogsPage에 탭(explorer·ai-analysis) UI 추가. explorer는 로그 목록/검색, ai-analysis는 챗봇 영역(스텁 가능). | SettingsLogsPage.tsx |
| H3 | 문서 동기화 | admin-dashboard.md에 "Phase H1 적용 시" 또는 "현재 설정은 전체 노출" 등 구현 상태 반영. | admin-dashboard.md |

### 12.4 통과 기준 (Gate H)

- admin이 아닌 사용자에게 설정 메뉴가 숨겨지거나 접근 시 403 처리된다. 로그 페이지에 탭 구조가 존재한다(실연동은 선택).

---

## 13. Phase I: 데이터소스 extract-metadata SSE 연동

**목표**: 데이터소스 "동기화"를 Weaver POST /api/datasources/{name}/extract-metadata SSE로 전환하고, 진행률(progress)·완료(neo4j_saved)·에러를 UI에 반영.

### 13.1 참조 설계

- **datasource-manager.md** §3: SSE 기반 동기화 진행률(phase·percent·테이블별), 연결됨/동기화중/오류 상태.
- **Weaver metadata-api.md**: POST extract-metadata, event: started, progress, schema_found, table_found, columns_extracted, fk_extracted, complete, neo4j_saved, error.

### 13.2 선행 조건

- Weaver POST /api/datasources/{name}/extract-metadata 구현 완료(Weaver W1–W9). 인증 토큰 전달 가능.

### 13.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| I1 | extract-metadata API 호출 | weaverDatasourceApi에 extractMetadataStream(name, options) 추가. EventSource 또는 fetch+ReadableStream로 SSE 구독. | weaverDatasourceApi.ts 또는 전용 stream 모듈 |
| I2 | SyncProgress를 SSE 진행률로 전환 | triggerSync 대신 extract-metadata 호출, event: progress 시 percent·phase 표시, complete/neo4j_saved 시 갱신, error 시 에러 메시지. | SyncProgress.tsx, useDatasources 또는 useExtractMetadata 훅 |
| I3 | legacy triggerSync 정리 | SyncProgress에서 legacy sync 제거 또는 fallback 정책(Weaver 미지원 시 legacy 유지). | SyncProgress.tsx, weaverDatasourceApi.ts |

### 13.4 통과 기준 (Gate I)

- 데이터소스 "동기화" 클릭 시 extract-metadata SSE가 호출되고, 진행률이 화면에 표시되며, 완료 시 카탈로그/Neo4j 저장 상태가 반영된다.

---

## 14. Phase J: Watch 규칙 CRUD·문서 정리

**목표**: Watch 알림 규칙 설정이 Core API와 일치하는지 검증하고, 미연동 시 문서화 또는 연동 완료.

### 14.1 참조 설계

- **watch-alerts.md**: AlertRuleEditor, 규칙 조건·대상·채널, SSE 구독.
- **02_api/watch-api.md** (Core): 규칙 CRUD 엔드포인트.

### 14.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| J1 | 규칙 CRUD API 연동 검증 | AlertRuleEditor가 사용하는 규칙 목록/생성/수정/삭제 API가 Core와 일치하는지 확인. | lib/api/watch.ts 또는 features/watch/api |
| J2 | 문서 정리 | watch-alerts.md에 "규칙은 Core GET/POST /api/v1/watches/rules 연동" 또는 Mock/스텁 명시. | watch-alerts.md |

### 14.3 통과 기준 (Gate J)

- 규칙 설정 시 Core API와 계약이 일치하거나, 문서에 현재 연동 상태가 명시된다.

---

## 15. Phase K: 문서 동기화 (routing, directory-structure)

**목표**: 04_frontend 내 라우팅·디렉토리 구조 문서를 실제 코드와 일치시키기.

### 15.1 참조 설계

- **routing.md**: 현재 구현은 createBrowserRouter(routeConfig.tsx), RouterProvider. 문서에는 "BrowserRouter + Routes"·"createBrowserRouter 미사용"으로 되어 있음.
- **directory-structure.md**: features/ 하위 api·hooks 구조. 실제는 lib/api/casesApi.ts 등 일부 중앙화·일부 feature만 api/ 보유.

### 15.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| K1 | routing.md 현행화 | createBrowserRouter, routeConfig.tsx, RouterProvider 반영. "구현 상태: Data Router 전환 완료(Phase G)". | routing.md |
| K2 | directory-structure.md 현행화 | 실제 디렉토리(lib/api vs features/*/api) 구조 반영. case-dashboard는 hooks/·components/ 중심, casesApi는 lib/api. | directory-structure.md |

### 15.3 통과 기준 (Gate K)

- routing.md·directory-structure.md를 코드 기준으로 읽었을 때 불일치가 없다.

---

## 16. 권장 실행 순서

1. **Phase K (문서 동기화)** — 문서만 수정, 즉시 적용 가능.
2. **Phase H (Admin 설정)** — 정책 확정 시 RoleGuard·로그 탭 구조 적용.
3. **Phase I (extract-metadata SSE)** — Weaver API 확정 후 데이터소스 동기화 UX 개선.
4. **Phase J (Watch 규칙)** — Core Watch 규칙 API 확인 후 연동 또는 문서 정리.

---

## 17. 문서 갱신

- 각 Phase 완료 시 **frontend-design-gap-analysis.md** 해당 갭을 "해소"로 갱신.
- **apps/canvas/docs/04_frontend/** 내 routing.md, directory-structure.md, admin-dashboard.md, datasource-manager.md, watch-alerts.md를 구현 상태에 맞게 수정.
- API 계약(02_api, service-endpoints-ssot)에 새로 사용하는 엔드포인트가 있으면 반영.
