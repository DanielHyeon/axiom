# 프론트엔드 UI/UX 갭 구현 계획

> **근거**: [docs/frontend-ui-ux-gap-status.md](../../frontend-ui-ux-gap-status.md)  
> **작성일**: 2026-02-22

## 1. 목표

설계 대비 미구현 항목을 우선순위에 따라 구현하여 에러 UI 일관성, 레이아웃(Header/UserMenu, Sidebar), 설정 하위 라우트, Feature 컴포넌트(PathHighlighter, ScenarioComparison)를 보완한다.

## 2. 티켓·산출물

| ID | 제목 | 산출 | 우선순위 |
|----|------|------|----------|
| U1 | ErrorPage를 GlobalErrorBoundary fallback으로 연동 | GlobalErrorBoundary가 에러 시 ErrorPage 렌더 | 높음 |
| U2 | Header + UserMenu 추가 | MainLayout 상단 헤더, 유저 이메일·로그아웃, NotificationBell | 높음 |
| U3 | Sidebar 컴포넌트 분리 | layouts/Sidebar.tsx (또는 SidebarNav), MainLayout에서 사용 | 중간 |
| U4 | 설정 /logs, /config 라우트·페이지 | ROUTES 확장, SettingsLogsPage, SettingsConfigPage, SettingsPage 탭 | 중간 |
| U5 | PathHighlighter (온톨로지) | 경로 하이라이트 UI, 2노드 선택 시 경로 표시 (연동은 훅/API 추후) | 중간 |
| U6 | ScenarioComparison (What-if) | 복수 시나리오 열 비교 테이블, WhatIfPage에서 사용 | 중간 |

## 3. 비적용 범위 (본 계획에서 제외)

- app/ 디렉터리 구조 변경, shared/ui 경로 통일
- createBrowserRouter 전환, i18n 도입, Design Tokens·다크 모드 전역
- 프로세스 디자이너 Minimap·PropertyPanel·Yjs·마이닝 오버레이
- Vitest/RTL 단위·통합 테스트 확대

### 3.1 제외 사유

| 항목 | 제외 이유 |
|------|-----------|
| **app/ 디렉터리, shared/ui 경로** | 진입점·import 경로를 전역으로 옮기는 **구조 변경**이라 영향 범위가 큼. 설계 문서와의 “경로 불일치”는 기능상 문제가 없어, 별도 마이그레이션 계획에서 다루는 편이 안전함. |
| **createBrowserRouter** | Data loader·errorElement 등 **라우터 패턴 전환**이 필요하고, 기존 BrowserRouter + Routes 동작을 바꾸면 회귀 위험이 있음. 라우팅이 현재 요구사항을 만족하므로 우선순위를 낮게 둠. |
| **i18n** | react-i18next 도입 시 **문자열 전역 치환**과 번역 리소스(ko/en) 관리가 필요함. 다국어 요구가 확정된 뒤 전용 계획으로 진행하는 편이 적절함. |
| **Design Tokens·다크 모드** | **전역 테마** 도입은 색·간격·타이포를 토큰화하고, 기존 하드코딩 스타일을 점진적으로 교체해야 함. 단일 스프린트보다는 디자인 시스템 단계에서 다루는 것이 맞음. |
| **프로세스 디자이너 Minimap·PropertyPanel·Yjs·마이닝** | **Feature 내부 완성도** 작업으로, 캔버스 좌표·상태·Synapse/백엔드 연동 등 맥락이 많음. 별도 “프로세스 디자이너 v2” 또는 스프린트에서 범위를 정해 진행하는 것이 좋음. |
| **Vitest/RTL 단위·통합 테스트** | 테스트 인프라·커버리지 확대는 **품질 전용** 작업. E2E(Playwright)는 이미 일부 존재하므로, 단위/통합은 품질 목표가 정해진 뒤 별도 계획으로 진행하는 것을 권장함. |

요약: **한 번에 적용하기엔 영향이 크거나(구조·라우터·테마), 범위가 feature/품질 전용인 항목**이라 본 계획에서는 제외했고, 필요 시 “구조 마이그레이션”, “i18n/디자인 시스템”, “프로세스 디자이너 고도화”, “테스트 확대” 등 **별도 계획**으로 진행하는 것을 전제로 둠.

## 4. 통과 기준

- 에러 발생 시 ErrorPage와 동일한 UI로 표시됨. ✅
- MainLayout에 헤더(알림·유저 메뉴·로그아웃) 표시됨. ✅
- Sidebar가 별도 컴포넌트로 분리되어 MainLayout이 참조함. ✅
- /settings/logs, /settings/config 접근 시 전용 페이지가 렌더됨. ✅
- 온톨로지 페이지에서 PathHighlighter 사용 가능, What-if 페이지에서 ScenarioComparison 사용 가능. ✅

## 5. 구현 완료 (2026-02-22)

| ID | 산출 |
|----|------|
| U1 | GlobalErrorBoundary → ErrorPage 렌더 |
| U2 | layouts/components/Header.tsx, UserMenu.tsx (NotificationBell + 유저·로그아웃) |
| U3 | layouts/Sidebar.tsx, MainLayout에서 Sidebar·Header 사용 |
| U4 | ROUTES.SETTINGS_LOGS, SETTINGS_CONFIG, SettingsLogsPage, SettingsConfigPage, SettingsPage 탭 4개 |
| U5 | pages/ontology/components/PathHighlighter.tsx, OntologyPage 연동 |
| U6 | pages/whatif/components/ScenarioComparison.tsx, WhatIfPage compare 테이블 연동 |

---

## 6. 추가로 구현할 사항 (미해소 갭·비적용 범위)

아래는 **아직 구현되지 않았거나**, 이번 계획에서 **비적용 범위로 둔** 항목이다. 필요 시 별도 스프린트/계획으로 진행한다.

### 6.1 갭 문서 기준 잔여 항목 (구현 가능)

| 항목 | 설명 | 우선순위 |
|------|------|----------|
| **대시보드에 CaseFilters** | CaseDashboardPage에 CaseFilters 추가(상태 필터). CaseListPage에만 있음. | 선택 |
| **RootLayout 도입** | RootLayout 컴포넌트로 감싸고, Auth/Dashboard 레이아웃을 자식으로 분리. | Low |
| **페이지 단위 ErrorBoundary** | 주요 라우트 또는 페이지별 ErrorBoundary 적용(에러 시 해당 페이지만 ErrorPage). | Medium |
| **폼 표준 (React Hook Form + Zod)** | 신규/수정 폼에 React Hook Form + Zod 적용 범위 확대. | Medium |
| **queryClient 전역 옵션** | retry, staleTime, mutation onError 등 TanStack Query 기본 옵션 정리·문서화. | Low |
| **wsManager / sseManager 표준화** | Watch·SSE 등 이벤트 스트림을 공통 매니저로 추상화 여부 검토. | Low |
| **설계 문서 동기화** | routing.md, directory-structure.md 등을 현재 코드 구조에 맞게 수정. | Low |

### 6.2 비적용 범위 (별도 계획 권장)

| 항목 | 비고 |
|------|------|
| **app/ 디렉터리, shared/ui 경로 통일** | 구조 마이그레이션 계획에서 진행. |
| **createBrowserRouter** | Data router 전환 시 별도 계획. |
| **i18n (react-i18next, ko/en)** | 다국어 요구 확정 후 i18n 전용 계획. |
| **Design Tokens·다크 모드** | 디자인 시스템/테마 계획에서 진행. |
| **프로세스 디자이너** Minimap·PropertyPanel·Yjs·ConformanceOverlay·VariantList | 프로세스 디자이너 고도화 스프린트. |
| **Vitest + RTL 단위·통합 테스트** | 품질 목표 정한 뒤 테스트 확대 계획. |
