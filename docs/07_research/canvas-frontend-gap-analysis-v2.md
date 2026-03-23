# Canvas 프론트엔드 현황 분석 및 구현 계획서 v2

> **작성일**: 2026-03-24
> **기준**: `feat/semantic-layer-v5.2` 브랜치 Canvas 소스 코드 (565 파일, 31 피처 모듈)
> **비교 대상**: `canvas/docs/04_frontend/feature-priority-matrix.md` + KAIR `robo-data-frontend` (269 파일, 19 기능)
> **목적**: 현재 구현 상태를 정밀 분석하고, 출시 준비도(readiness) 기반 우선순위로 구현 계획을 수립한다.

**본 문서의 원칙**:
- 구현율(코드 존재 여부)과 출시 준비도(readiness)를 분리한다.
- 각 피처는 7단계 상태로 분류한다 (§1.2 참조).
- 각 Phase는 Entry/Exit Criteria 게이트로 통제한다.
- KAIR 기능 이식은 parity 자체를 목표로 하지 않고, Canvas 제품 전략과 사용자 가치에 직접 연결되는 기능만 선별 도입한다.
- 본문은 최신 상태만 기술한다. 변경 이력은 §14 Changelog에 분리한다.

---

## 목차

1. [전체 현황 요약](#1-전체-현황-요약)
2. [상태 분류 체계 (Status Taxonomy)](#2-상태-분류-체계)
3. [인프라 현황](#3-인프라-현황)
4. [Feature별 상세 분석](#4-feature별-상세-분석)
5. [KAIR 대비 갭 분석](#5-kair-대비-갭-분석)
6. [UI/UX 품질 감사](#6-uiux-품질-감사)
7. [프론트엔드 운영 관측성](#7-프론트엔드-운영-관측성)
8. [i18n · 테넌시 · 권한 보안 검증](#8-i18n--테넌시--권한-보안-검증)
9. [구현 로드맵](#9-구현-로드맵)
10. [Phase별 Entry / Exit Criteria](#10-phase별-entry--exit-criteria)
11. [성공 지표](#11-성공-지표)
12. [리스크 & 의존성](#12-리스크--의존성)
13. [결정 사항](#13-결정-사항)
14. [Changelog](#14-changelog)

---

## 1. 전체 현황 요약

### 1.1 코드베이스 규모

| 지표 | 수량 |
|------|------|
| 총 TypeScript/TSX 파일 | 565 |
| Feature 모듈 | 31개 디렉토리 |
| Page 컴포넌트 | 68개 (24개 라우트 섹션) |
| shadcn/ui 컴포넌트 | 15개 |
| 공유 컴포넌트 | DataTable, EmptyState, ErrorState, LoadingSkeleton, AuthGuard, RoleGuard, MermaidERDRenderer |
| Zustand 스토어 | 8+ (전역 3 + 피처별 5+) |
| 테스트 파일 | 17개 |
| i18n 언어 | 2 (ko/en) |

---

## 2. 상태 분류 체계

> 단순 구현율(%) 대신, 출시 가능성을 판단하기 위한 7단계 상태를 사용한다.

| 상태 코드 | 의미 | 출시 가능? |
|-----------|------|:----------:|
| **II** (Implemented-Integrated) | UI + 실 API 연동 + 상태관리 완비 | ✅ 가능 |
| **ID** (Implemented-Disconnected) | UI 완성, API 호출 코드 있으나 엔드포인트 미검증 | ⚠️ 검증 후 |
| **MB** (Mock-Backed) | UI 완성, mock 데이터 기반 동작 | ❌ API 연결 필요 |
| **UO** (UI-Only) | 컴포넌트 존재하나 훅/스토어/API 미연결 | ❌ 연결 필요 |
| **RF** (Reusable-from-other) | 다른 피처에 유사 기능 존재, 재사용 가능 | ⚠️ 리팩토링 후 |
| **BB** (Blocked-by-backend) | 프론트 준비됐으나 백엔드 API 미구현 | ❌ 백엔드 대기 |
| **NS** (Not-started) | 코드 없음 | ❌ 신규 구현 |

**추가 태그** (상태와 독립적으로 부착):
- `[needs-test]` — 단위/E2E 테스트 없음
- `[needs-a11y]` — 접근성 미검증
- `[needs-perf]` — 성능 미검증 (대량 데이터, 캔버스 등)
- `[needs-i18n]` — 하드코딩 문자열 존재

---

## 3. 인프라 현황

| 영역 | 상태 | 파일 |
|------|:----:|------|
| 디자인 시스템 (shadcn/ui) | **II** | `components/ui/` (15개) |
| Design Tokens (CSS 변수, 다크모드) | **ID** | `styles/tokens.css` + `index.css` — 토큰 정의 완료, 40+ 파일에서 미채택 |
| 레이아웃 (Root/Dashboard/Auth) | **II** | `layouts/` (11 파일) — 단, DashboardLayout.tsx는 dead code |
| 라우팅 + lazy loading | **II** | `lib/routes/routeConfig.tsx` |
| API 클라이언트 + JWT 인터셉터 | **II** | `lib/api-client.ts`, `lib/api/` |
| 공유 DataTable (TanStack Table 래퍼) | **II** | `components/shared/DataTable.tsx` (80 LOC) |
| Zustand 전역 스토어 | **II** | `stores/authStore.ts`, `themeStore.ts` |
| TanStack Query 설정 | **II** | `lib/queryClient.ts` |
| WebSocket 매니저 | **II** | `lib/wsManager.ts`, `lib/streamManager.ts` |
| i18n (ko/en) | **II** | `lib/i18n/` — 단, 신규 코드에 하드코딩 문자열 존재 |
| 에러 바운더리 | **II** | `components/GlobalErrorBoundary.tsx` |
| Toast (sonner) | **ID** | sonner 사용 — 일부 페이지 `console.error`만 사용 |
| E2E 테스트 (Playwright) | **NS** | 미설정 |
| 접근성 자동화 (axe-core) | **NS** | 미설치 |
| FE 에러 추적 (Sentry 등) | **NS** | 미설정 |

---

## 4. Feature별 상세 분석

### 4.1 종합 매트릭스

> **파일 수 카운트 기준**: `features/<name>/` + `pages/<name>/` 합산. 별도 표기 시 `(feat N + pages M)` 형식.

| Feature | 파일 수 | 상태 | 출시 준비도 | 태그 | 잔여 갭 요약 |
|---------|:------:|:----:|:----------:|------|-------------|
| 인증/인가 | 3(page)+6(shared) | **II** | **높음** | `[needs-test]` | features/auth/ 정리, 테스트 |
| 케이스 대시보드 | 15 | **ID** | **중간** | `[needs-test]` | DashboardComposer, 역할별 패널 3개, WS 연동 |
| 문서 관리+HITL | 8 | **MB** | **낮음** | `[needs-test]` `[needs-a11y]` | mock→실API, HITL FSM 가드, 낙관적 업데이트 |
| NL2SQL | 38 | **ID** | **높음** | `[needs-a11y]` | ChartRecommender |
| OLAP 피벗 | 25 | **ID** | **높음** | `[needs-a11y]` | CSV Export UI, DnD 접근성 |
| Watch 알림 | 14 (feat 6+pages 8) | **ID** | **중간** | `[needs-test]` | AlertFeed/Stats/RuleEditor는 pages/watch/에 존재. API 연동 검증 + 심각도별 토스트 세분화 |
| 데이터소스 관리 | 12 | **ID** | **중간** | `[needs-test]` | ConnectionForm Dialog, DatasourceCard |
| 프로세스 디자이너 | 41 | **II** | **높음** | `[needs-test]` `[needs-perf]` | Minimap, 뷰포트 컬링 |
| What-if 시나리오 | 34 (feat 27+pages 7) | **ID** | **중간** | `[needs-test]` | TornadoChart, ScenarioComparison |
| 온톨로지 브라우저 | 15 | **UO** | **낮음** | `[needs-test]` | SearchPanel, LayerFilter, NodeDetail, PathHighlighter |
| 시맨틱 카탈로그 | 15 | **ID** | **중간** | | 스냅샷 빌더 UI, 아티팩트 검사 |
| 워크플로 에디터 | 15 | **ID** | **중간** | `[needs-test]` | API 연동, 순환참조 검증, 스케줄링 |
| CEP 규칙 | 4 | **ID** | **중간** | | LLM 대화형 규칙 정의 오버레이 |
| 보안/권한 관리 | 14 | **ID** | **중간** | | 백엔드 API 연동 검증 |
| 데이터 품질 | 10 | **ID** | **중간** | | DQ 스캔 트리거, 규칙 실행 연동 |
| 인제스트/업로드 | 13 | **ID** | **중간** | | 언어별 파일 감지, 파이프라인 라이프사이클 |
| 리니지 | 10 | **UO** | **낮음** | | 소스코드 링크, 프로시저 의존성 |
| Insight (KPI 분석) | 20 | **ID** | **중간** | | 백엔드 API 일부 미구현 (GET /kpis, /drivers) |
| 글로서리 | 11 | **ID** | **중간** | | |
| 도메인 모델러 | 11+16 | **ID** | **중간** | | |
| 오브젝트 탐색기 | 11 | **UO** | **낮음** | | 메트릭 차트 없음 |
| 피드백 | 7 | **ID** | **중간** | | |
| 복원력 UI | 1 | **UO** | **낮음** | | Graceful Degradation, Circuit Breaker |

### 4.2 출시 준비도별 분류

| 준비도 | Feature 수 | 설명 |
|--------|:---------:|------|
| **높음** (시연/출시 가능) | 4 | 인증, NL2SQL, OLAP, 프로세스 디자이너 |
| **중간** (API 검증/보완 후 가능) | 14 | 대시보드, Watch, 데이터소스, What-if, 시맨틱 카탈로그, 워크플로 등 |
| **낮음** (핵심 작업 필요) | 4 | 문서HITL, 온톨로지, 리니지, 복원력 |

---

## 5. KAIR 대비 갭 분석

> KAIR `robo-data-frontend` 19개 기능 영역과 1:1 교차 비교. Canvas 제품 전략과 무관한 기능은 이식하지 않음.

### 5.1 교차 비교 매트릭스

| # | KAIR 기능 | Canvas 상태 | 잔여 갭 | 이식 판정 |
|---|----------|:-----------:|---------|:---------:|
| 1 | 파일 업로드 + 코드 인제스트 | **ID** | 언어별 파일 감지 (Java/Python/PL-SQL/DDL) | ✅ 이식 |
| 2 | 스키마 캔버스 ERD | **ID** | 인터랙티브 TableCard (드래그), 관계 소스 배지 | ⚠️ 선택 |
| 3 | 데이터 리니지 UI | **UO** | 프로시저→테이블 의존성, 소스코드 클릭→라인 | ✅ 이식 |
| 4 | 그래프 시각화 (Neo4j) | **II** | PNG/SVG/JSON 내보내기 | ⚠️ 선택 |
| 5 | **DMN 결정 에디터** | **NS** | 전체 미구현 | ✅ 이식 |
| 6 | **비즈니스 캘린더** | **NS** | 전체 미구현 | ✅ 이식 |
| 7 | AI 이벤트 탐지 | **ID** | LLM 대화형 규칙 정의 오버레이 (기반 CRUD 완성 642 LOC) | ⚠️ 선택 |
| 8 | 관찰성 워크플로 빌더 | **ID** | API 연동 + 순환참조 검증 + 스케줄링 (기반 1,768 LOC 완성) | ✅ 이식 |
| 9 | 파이프라인 제어 | **ID** | pause/resume/stop 백엔드 연동 | ✅ 이식 |
| 10 | SSE 스트리밍 진행 UI | **ID** | 실 SSE/NDJSON 연동 (현재 폴링) | ⚠️ 선택 |
| 11 | BPMN 뷰어 | **NS** | 전체 미구현 (Konva 프로세스 디자이너가 대체) | ❌ 보류 |
| 12 | 그래프 내보내기 | **RF** | PNG/SVG/JSON 다중 포맷 (ERD SVG만 존재) | ⚠️ 선택 |
| 13 | 오브젝트 탐색기 + 차트 | **UO** | 메트릭 차트 시각화 | ⚠️ 선택 |
| 14 | 소스코드 뷰어 | **ID** | 클릭→라인 네비게이션 (display-only 뷰어 존재) | ⚠️ 선택 |
| 15 | 인과 분석 UI | **ID** | VAR 모델링 UI, lag 시각화, 신뢰도 히트맵 | ✅ 이식 |

### 5.2 이식 판정 요약

| 판정 | 건수 | 기능 |
|------|:----:|------|
| ✅ 이식 (제품 가치 직결) | 7 | DMN, 캘린더, 워크플로 연동, 파이프라인, 파일 감지, 리니지 소스링크, 인과분석 |
| ⚠️ 선택 (P2 이후 검토) | 7 | 스키마 고도화, AI 이벤트, SSE, 그래프 내보내기, 오브젝트 차트 등 |
| ❌ 보류 (대체 존재) | 1 | BPMN (Konva 프로세스 디자이너가 대체) |

### 5.3 이식 대상 신규 구현 상세

| ID | 기능 | 신규 파일 | 수정 파일 | LOC |
|----|------|:--------:|:--------:|:---:|
| KG-1 | DMN 결정 에디터 (타입+API+훅+에디터+테스트러너) | 7 | 0 | ~730 |
| KG-2 | 비즈니스 캘린더 (캘린더 그리드+공휴일 에디터) | 6 | 0 | ~540 |
| KG-3 | 워크플로 빌더 잔여 (API 연동+검증+스케줄링) | 1 | 2 | ~190 |
| KG-6 | 리니지 소스코드 링크 (프로시저 의존성+클릭→라인) | 2 | 1 | ~300 |
| KG-7 | 인과 분석 시각화 (VAR UI+lag 차트+신뢰도) | 3 | 0 | ~400 |
| KG-9 | 그래프 내보내기 (PNG/SVG/JSON 공용 훅) | 1 | 0 | ~120 |
| KG-10 | 파일 언어 감지 (Java/Python/PL-SQL/DDL 자동 분류) | 0 | 2 | ~200 |
| **합계** | | **20** | **5** | **~2,480** |

---

## 6. UI/UX 품질 감사

### 6.1 정량 평가 (가중 점수)

| 지표 | 측정값 | 배점 | 점수 | 산식 |
|------|--------|:----:|:----:|------|
| 디자인 토큰 준수율 | 40+ 파일에서 195건 하드코딩 | 20 | 6 | (565-40)/565 × 20 ≈ 18.6 → 하드코딩 비율 감점 |
| 하드코딩 색상 0건 여부 | 195건 | 10 | 0 | 0건이어야 만점 |
| ARIA 속성 밀도 | 55건/565파일 = 0.097/파일 | 10 | 2 | 목표 0.5/파일 대비 19% |
| Skip navigation link | 없음 | 5 | 0 | 유무 |
| Dialog focus trap | stub (Radix 미사용) | 5 | 0 | 유무 |
| Page title 관리 | 없음 (동일 탭 제목) | 5 | 0 | 유무 |
| route-level empty/loading/error 완비율 | ~50% (일부 페이지만) | 10 | 5 | 비율 × 10 |
| Breakpoint 적용률 | 41건/565파일 = 7% | 10 | 1 | 목표 50% 대비 |
| `prefers-reduced-motion` 지원 | 없음 | 5 | 0 | 유무 |
| Dead code 부재 | 4건 (DashboardLayout, App.css 등) | 5 | 3 | (목표0 - 4건) 감점 |
| Glass morphism 폴백 | 없음 | 5 | 0 | 유무 |
| 폰트 로딩 전략 | 미확인 | 5 | 2 | 부분 |
| 사이드바 그룹핑 | 없음 (17개 flat) | 5 | 0 | 유무 |
| **합계** | | **100** | **19** | |

> **정량 점수: 19/100.** 이 점수는 측정 가능한 항목만 반영한다. 디자인 시스템 기반 완성도, 코드 구조 품질, 기존 UX 패턴(글래스 모피즘, 스켈레톤 로딩 등) 같은 정성 항목은 별도 평가가 필요하며, 정량 점수와 혼합하지 않는다.

### 6.2 CRITICAL 이슈 (5건)

| # | 문제 | 파일 | 수정 공수 |
|---|------|------|:--------:|
| C1 | 다크모드 깨짐 — 195건 하드코딩 색상 | 40+ 파일 | 2-3일 |
| C2 | Skip navigation 없음 (WCAG 2.4.1) | `MainLayout.tsx` | 15분 |
| C3 | Dialog stub — focus trap/Escape/ARIA 없음 | `components/ui/dialog.tsx` | 30분 |
| C4 | Dead code — DashboardLayout, App.css, DashboardPage, AuthLayout | 4 파일 | 1시간 |
| C5 | 에러 페이지 오타 `text-foreground0` | NotFoundPage, ErrorPage | 5분 |

### 6.3 HIGH 이슈 (7건)

| # | 문제 | 수정 공수 |
|---|------|:--------:|
| H1 | 반응형 디자인 부재 (41 breakpoint, 모바일 무시) | 3-5일 |
| H2 | 스크린 리더 지원 최소 (sr-only 6건, aria 55건) | 1-2일 |
| H3 | 페이지 레이아웃 불일치 (3 패딩, 4 제목 크기) — PageShell 필요 | 1-2일 |
| H4 | DashboardPage 깨진 플레이스홀더 (`JSON.stringify` 렌더) | 15분 |
| H5 | `prefers-reduced-motion` 미지원 | 5분 |
| H6 | Glass morphism `@supports` 폴백 없음 | 15분 |
| H7 | 사이드바 17개 항목 그룹핑 없음 | 10분 |

---

## 7. 프론트엔드 운영 관측성

> 테스트와 별개로, 운영 환경에서 오류를 수집하고 성능을 관측하는 인프라.

| 영역 | 현재 | 목표 | 도구 후보 |
|------|:----:|------|----------|
| FE 에러 추적 | **NS** | route-level 에러 캡처 + 사용자 컨텍스트 | Sentry, LogRocket |
| 성능 트레이싱 | **NS** | Web Vitals (LCP/FID/CLS) 자동 수집 | `web-vitals` + 커스텀 리포터 |
| WebSocket 재연결 텔레메트리 | **NS** | 재연결 빈도, 드롭 이벤트 카운트 | wsManager 내 메트릭 추가 |
| Mutation 실패 로깅 | **NS** | TanStack Query onError 글로벌 핸들러 | queryClient 기본 옵션 |
| 번들 크기 모니터링 | **NS** | PR별 번들 diff 리포트 | `vite-plugin-visualizer` + CI |

**구현 시점**: Phase 1(테스트 기반 강화)와 동시에 최소 에러 추적 + Web Vitals를 설정한다.

---

## 8. i18n · 테넌시 · 권한 보안 검증

### 8.1 i18n 규칙

| 규칙 | 현재 상태 |
|------|----------|
| 모든 신규 UI는 i18n key 기반으로만 작성, 하드코딩 문자열 금지 | ⚠️ 기존 코드에 하드코딩 한글/영어 산재 |
| ko.json / en.json 키 동기화 검증 | ❌ 자동 검증 없음 |
| 날짜/숫자 로캘 포매팅 | ⚠️ 부분 적용 |

### 8.2 권한 4계층 검증

| 계층 | 현재 상태 | 검증 방법 |
|------|----------|----------|
| **라우트 가드** | ✅ ProtectedRoute + RoleGuard | E2E: 권한 없는 라우트 접근 → 리다이렉트 |
| **메뉴 필터링** | ✅ Sidebar 역할별 필터 | 단위: 7개 역할별 메뉴 항목 확인 |
| **버튼/액션 숨김** | ⚠️ 일부 usePermission 사용, 일부 누락 | 감사: 모든 mutation 버튼에 permission guard 확인 |
| **API 요청 헤더** | ✅ X-Tenant-Id 인터셉터 | 단위: 테넌트 헤더 누락/변조 케이스 테스트 |

### 8.3 멀티테넌트 보안 테스트 매트릭스

| 테스트 케이스 | 우선순위 |
|-------------|:--------:|
| X-Tenant-Id 헤더 없이 API 호출 → 403 확인 | P0 |
| 다른 테넌트 ID로 API 호출 → 데이터 격리 확인 | P0 |
| JWT 만료 후 자동 갱신 → 세션 유지 확인 | P0 |
| 역할 없는 사용자로 admin 페이지 접근 → 리다이렉트 | P0 |
| mutation 버튼 클릭 시 권한 미달 → 적절한 에러 메시지 | P1 |

---

## 9. 구현 로드맵

### 9.0 실행 순서 원칙

> "어떤 순서로 해야 총 리스크가 가장 낮은가"

1. **Phase 0**: 문서/계약 정합성 → 모든 후속 작업의 품질 기반
2. **Phase 1**: P0 기능 완성 + Quick Wins → 최소 출시 가능 상태
3. **Phase 2**: 테스트/접근성/토큰 안정화 → 회귀 방지 기반 (기능 확장 전에 선행)
4. **Phase 3**: P1 기능 완성 → 분석/알림 확장
5. **Phase 4**: KAIR 이식 + P2 기능 → 차별화 확장
6. **Phase 5**: UX 체계 개선 → 디자인 토큰 퍼지, 반응형, 관측성

```
Phase 0 (3일) — 계약/기준 정립
  ├─ API/WebSocket 계약표 작성 (mock ↔ real 차이 분석)
  ├─ 상태 taxonomy 통일 (본 문서 §2 기준)
  ├─ 공통 DoD 정의 (완료 = UI + API + 테스트 + a11y + i18n)
  └─ ESLint 규칙: no-hardcoded-color, no-hardcoded-string

Phase 1 (2주) — P0 기능 완성 + Quick Wins
  ├─ Sprint 1a: 문서 관리 HITL (mock→real, FSM 가드, 낙관적 업데이트)
  ├─ Sprint 1b: 케이스 대시보드 패널 (DashboardComposer + 역할별 3개 패널)
  └─ Sprint 1c: UI Quick Wins (C2~C5, H4~H7 — 총 8건, 2시간)

Phase 2 (1주) — 테스트/품질 기반 강화
  ├─ Playwright 설정 + 핵심 E2E 3개 (로그인→대시보드→문서HITL)
  ├─ 고위험 플로우 단위 테스트 (authStore, HITL FSM, WS 처리, 테넌트 헤더)
  ├─ axe-core 자동 스캔 통합
  ├─ Dialog → @radix-ui/react-dialog 교체 (C3)
  └─ FE 에러 추적 + Web Vitals 설정

Phase 3 (2주) — P1 기능 완성
  ├─ Sprint 3a: Watch 알림 UI (AlertFeed, Stats, RuleEditor, NotificationBell)
  ├─ Sprint 3b: NL2SQL ChartRecommender + OLAP CSV Export + DnD 접근성
  └─ Sprint 3c: 데이터소스 ConnectionForm + TestConnection

Phase 4 (2주) — KAIR 이식 + P2 기능
  ├─ Sprint 4a: DMN 결정 에디터 (KG-1) + 비즈니스 캘린더 (KG-2) ← 병렬
  ├─ Sprint 4b: 온톨로지 그래프 탐색 UI + 리니지 소스코드 링크 (KG-6)
  └─ Sprint 4c: 인과 분석 시각화 (KG-7) + 워크플로 잔여 (KG-3) + 파일 감지 (KG-10)

Phase 5 (2주) — UX 체계 개선
  ├─ Sprint 5a: 하드코딩 색상 퍼지 (195건 → 디자인 토큰 치환) + PageShell
  ├─ Sprint 5b: 반응형 디자인 패스 (전 페이지 sm:/md:/lg:)
  └─ Sprint 5c: 사이드바 그룹핑 + 브라우저 탭 제목 + 폰트 로딩 검증
```

---

## 10. Phase별 Entry / Exit Criteria

### Phase 0: 계약/기준 정립

| Entry | Exit |
|-------|------|
| 없음 (첫 Phase) | API 계약표 완성 (엔드포인트별 mock/real 상태 + 페이로드 차이) |
| | 상태 taxonomy 7단계가 모든 피처에 적용됨 |
| | ESLint 규칙 2개 (no-hardcoded-color, no-hardcoded-string) CI에 활성 |
| | 공통 DoD 문서 팀 합의 |

### Phase 1: P0 기능 완성

| Entry | Exit |
|-------|------|
| 문서 API 스펙 확정 (Core: documents CRUD + status transition) | draft→review→approved/rejected가 UI+API+테스트에서 일관 동작 |
| 문서 상태 전이 이벤트 정의 (WebSocket payload) | 케이스 대시보드 7개 역할별 패널 표시 확인 |
| mock payload ↔ real payload 차이 표 작성 | Quick Wins 8건 적용 완료 |
| | 문서 관리 상태: **MB** → **ID** 이상 |

### Phase 2: 테스트/품질 기반

| Entry | Exit |
|-------|------|
| Phase 1 Exit Criteria 충족 | Playwright E2E 3개 핵심 경로 통과 |
| | 고위험 플로우 5개 단위 테스트 존재 |
| | axe-core Critical/Serious 0건 |
| | Dialog 컴포넌트 Radix 교체 완료 |
| | FE 에러 추적 동작 확인 |

### Phase 3: P1 기능 완성

| Entry | Exit |
|-------|------|
| Watch WebSocket 이벤트 스키마 버전 고정 | Watch AlertFeed + 심각도별 토스트 동작 |
| severity → 토스트 매핑 표 확정 | NL2SQL ChartRecommender 3개 차트 타입 추천 |
| NL2SQL/OLAP 백엔드 API 안정 | OLAP CSV 다운로드 + DnD 키보드 접근성 |

### Phase 4: KAIR 이식

| Entry | Exit |
|-------|------|
| Synapse DMN API 스펙 확정 | DMN 테이블 CRUD + 테스트 실행 동작 |
| Vision Calendar API 스펙 확정 | 캘린더 공휴일 CRUD + 영업일 계산 동작 |
| Core Alert DAG API 스펙 확정 | 워크플로 저장/로드 + 순환참조 검증 |

### Phase 5: UX 체계 개선

| Entry | Exit |
|-------|------|
| Phase 2 ESLint 규칙 활성 | 하드코딩 색상 0건 (ESLint CI 통과) |
| | 반응형 breakpoint 200건+ |
| | 다크모드 전 화면 스크린샷 비교 통과 |

---

## 11. 성공 지표

### 11.1 기능 지표

| 지표 | 현재 | 목표 | 측정 방법 |
|------|:----:|:----:|----------|
| P0 Feature 출시 준비도 | MB/ID | **II** | 상태 taxonomy |
| 전체 Feature 출시 준비도 | 4 II | **12+ II** | 상태 taxonomy |
| KAIR 이식 대상 완료 | 0/7 | **7/7** | KG-1~KG-10 중 이식 판정 건 |

### 11.2 품질 지표

| 지표 | 현재 | 목표 | 측정 방법 |
|------|:----:|:----:|----------|
| axe-core Critical/Serious | 미측정 | **0건** | CI 자동 스캔 |
| 하드코딩 색상 | 195건 | **0건** | ESLint 규칙 |
| ARIA 속성 밀도 | 0.097/파일 | **0.3+/파일** | grep 카운트 |
| UI/UX 정량 점수 | 19/100 | **65+/100** | §6.1 산식 (정량 항목만, 정성 제외) |

### 11.3 테스트 지표 (위험 기반)

> 전체 커버리지 %보다 고위험 플로우 100% 보호가 우선.

| 고위험 플로우 | 테스트 유형 | 현재 | 목표 |
|-------------|:---------:|:----:|:----:|
| 권한 가드 (라우트+메뉴+버튼+API) | 단위+E2E | ❌ | ✅ |
| HITL FSM (상태 전이 가드) | 단위 | ❌ | ✅ |
| WebSocket 처리 (연결/재연결/이벤트) | 단위 | ❌ | ✅ |
| 저장/롤백 (낙관적 업데이트) | 단위 | ❌ | ✅ |
| 멀티테넌트 헤더 | 단위 | ❌ | ✅ |
| Query 무효화 (mutation → 목록 갱신) | 단위 | ❌ | ✅ |
| 로그인→대시보드→문서→HITL | E2E | ❌ | ✅ |
| 로그인→NL2SQL→결과→차트 | E2E | ❌ | ✅ |
| 역할별 로그인→패널 확인 | E2E | ❌ | ✅ |

### 11.4 성능 지표 (라우트별 번들 예산)

> 전체 앱 단일 예산 대신, 라우트/청크별 예산으로 측정.

| 라우트 청크 | 예산 (gzipped) | 주요 의존성 |
|------------|:--------------:|------------|
| 로그인/대시보드 (초기 로드) | **< 150KB** | React, Zustand, TanStack Query |
| NL2SQL/분석 | **< 300KB** | + Cytoscape, Recharts |
| 프로세스 디자이너 | **< 400KB** | + Konva, Yjs |
| 문서 편집 | **< 350KB** | + Monaco |
| OLAP Studio | **< 300KB** | + Recharts, DnD |

---

## 12. 리스크 & 의존성

| 리스크 | 영향 | 대응 | 게이트 |
|--------|------|------|--------|
| 문서 관리 Core API 미구현 | P0 기능 동작 불가 | Mock 우선 → Phase 0에서 계약표 작성 → 백엔드 병행 | Phase 1 Entry |
| Watch WebSocket 스키마 불일치 | 실시간 알림 실패 | Phase 0에서 스키마 버전 고정 | Phase 3 Entry |
| 하드코딩 색상 퍼지 회귀 | 수정 중 기능 깨짐 | ESLint 규칙 선행 + 파일별 incremental + visual diff | Phase 5 Entry |
| 다크모드 검증 수동 의존 | 미발견 깨짐 | Chromatic 또는 스크린샷 비교 자동화 | Phase 5 Exit |
| Radix Dialog 교체 사용처 깨짐 | 모달 동작 변경 | 사용처 전수 조사 후 일괄 교체 | Phase 2 |
| 프로세스 디자이너 200노드 성능 | 프레임 드롭 | react-konva 가상화 + LOD | Phase 4 이후 |
| 번들 예산 초과 (Monaco+Konva+Cytoscape) | 초기 로드 지연 | lazy loading 검증 + tree-shaking 확인 | Phase 5 Exit |

---

## 13. 결정 사항

| 결정 | 근거 |
|------|------|
| 구현율과 출시 준비도를 분리한다 | 같은 80%라도 mock 기반 vs 실 API 연동은 출시 가능성이 완전히 다름 |
| 테스트/접근성을 Phase 2로 앞당긴다 | P0 연결 시작 시점에 회귀 폭증. 초기에 틀을 잡아야 후속 확장이 안전 |
| KAIR 이식은 Phase 4로 배치한다 | P0/P1 완성 + 테스트 기반 확보 전에 새 기능을 끌어오면 집중력 분산 |
| BPMN 뷰어는 보류한다 | Konva 프로세스 디자이너가 대체. 3번째 캔버스 라이브러리 추가는 유지보수 부담 |
| 전체 커버리지 % 대신 위험 기반 테스트 매트릭스를 사용한다 | 고위험 플로우 100% 보호가 전체 30%보다 실효성 높음 |
| 번들 예산은 라우트/청크별로 측정한다 | 전체 앱 200KB는 비현실적 (Monaco+Konva+Cytoscape 혼재) |
| 모든 신규 UI는 i18n key 기반, 하드코딩 문자열 금지 | 엔터프라이즈 국제화 품질 보장 |
| 권한 가드는 라우트·메뉴·버튼·API 4계층 검증 | 어느 한 계층이라도 누락되면 보안 사고 가능 |

---

## 14. Changelog

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-03-24 | v2.0 | 전면 재작성. 8가지 보강 반영: (1) 내부 충돌 제거, 최신 상태만 본문에 유지 (2) 7단계 상태 taxonomy + 출시 준비도 분리 (3) Phase별 Entry/Exit Criteria 추가 (4) 우선순위 재배치: Phase 0(계약) → Phase 2(테스트) 앞당김, KAIR 이식 Phase 4로 후배치 (5) 성능 지표 라우트별 번들 예산, 위험 기반 테스트 매트릭스 (6) UX 감사 정량 산식 추가 (7) 프론트엔드 운영 관측성 섹션 신설 (8) i18n/테넌시/권한 4계층 검증 섹션 신설 |
| 2026-03-24 | v1.4 | 리뷰 수정: workflow-editor(15파일/1,768 LOC) + CEP(4파일/765 LOC) 실 구현 확인. 전체 미구현 4→2건 |
| 2026-03-24 | v1.3 | KAIR 19개 기능 교차 비교 추가. Phase F 로드맵 |
| 2026-03-24 | v1.2 | UI/UX 감사 결과 추가. Phase E 로드맵 |
| 2026-03-24 | v1.1 | 리뷰 수정: 문서 관리 25%→65%, 공유 DataTable 존재 확인, 누락 15개 피처 추가 |
| 2026-03-23 | v1.0 | 초기 작성 |

---

## 총 구현 규모 요약

| Phase | 신규 파일 | 수정 파일 | LOC | 기간 |
|-------|:--------:|:--------:|:---:|:----:|
| Phase 0 (계약/기준) | 0 | 2 | ~100 | 3일 |
| Phase 1 (P0 기능) | ~8 | ~6 | ~1,200 | 2주 |
| Phase 2 (테스트/품질) | ~8 | ~5 | ~800 | 1주 |
| Phase 3 (P1 기능) | ~13 | ~4 | ~1,700 | 2주 |
| Phase 4 (KAIR 이식+P2) | ~28 | ~8 | ~3,080 | 2주 |
| Phase 5 (UX 체계) | ~3 | ~45 | ~1,800 | 2주 |
| **합계** | **~60** | **~70** | **~8,680** | **~9.5주** |
