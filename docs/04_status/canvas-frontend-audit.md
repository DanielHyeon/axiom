# Canvas 프론트엔드 심층 감사 보고서

> 작성일: 2026-03-20
> 대상: `canvas/src/` (263개 소스 파일)
> 빌드: TypeScript 에러 0건

---

## 1. 요약

| 카테고리 | 상태 | 발견 수 |
|----------|------|---------|
| 미구현/스텁 코드 | 🔴 | 5건 (API 갭) |
| 에러 핸들링 | 🟡 | 8건 (silent fail) |
| 접근성 (a11y) | 🔴 | 다수 (aria-label 누락) |
| 반응형 디자인 | 🟡 | 3건 (모바일 미대응) |
| 성능 최적화 | 🟡 | 4건 (메모이제이션 누락) |
| 타입 안전성 | 🔴 | @ts-nocheck 4파일, any 다수 |
| 코드 중복 | 🟡 | 3개 패턴 반복 |
| 보안 | 🟢 | 양호 (JWT, Tenant 격리) |
| UX 완성도 | 🟡 | 빈 상태/에러 상태 부분 누락 |
| 국제화 (i18n) | 🔴 | 인프라 있으나 리소스 없음 |
| 테스트 | 🔴 | 단위 테스트 거의 없음 |
| 백엔드 API 갭 | 🟡 | 5개 엔드포인트 |

---

## 2. P0: 긴급 개선 사항

### 2.1 @ts-nocheck 제거 (타입 안전성)

**영향 파일:**
- `pages/insight/InsightPage.tsx`
- `pages/nl2sql/Nl2SqlPage.tsx`
- `pages/ontology/components/GraphViewer.tsx`
- `pages/nl2sql/components/ReactProgressTimeline.tsx`

**현상**: `// @ts-nocheck`로 전체 파일 타입 검사 비활성화. TypeScript strict mode의 의미가 사라짐.

**조치**:
- 각 파일에서 `@ts-nocheck` 제거
- Cytoscape API 관련 타입 이슈는 `as cytoscape.Css.Node` 타입 단언으로 해결
- NDJSON 스트림 데이터는 `Record<string, unknown>` + 타입 가드로 처리

**우선순위**: P0 — 타입 오류가 숨겨져 런타임 버그로 이어질 수 있음

---

### 2.2 Insight API 백엔드 갭 해소

| 엔드포인트 | 상태 | 현재 대안 | 영향 |
|-----------|------|----------|------|
| `GET /api/insight/kpis` | ❌ 미구현 | KpiSelector 하드코딩 샘플 | KPI 선택이 정적 |
| `GET /api/insight/drivers` | ❌ 미구현 | 클라이언트에서 graph 노드 파생 | 정확도 낮음 |
| `GET /api/insight/nodes/{id}` | ❌ 미구현 | useDriverDetail이 stub | Detail 패널 비어있음 |
| `POST /api/insight/logs:ingest` | ❌ 미구현 | Oracle→Weaver 자동 연동 없음 | 수동 업로드만 |
| `GET /api/insight/schema-coverage` | 정의만 | 미사용 | 기능 없음 |

**조치**: Weaver 서비스에 해당 엔드포인트 구현 필요

---

### 2.3 에러 핸들링 Silent Fail 제거

**문제 파일:**

| 파일 | 위치 | 현상 |
|------|------|------|
| `useDriverDetail.ts` | catch 블록 | `.catch(() => setDetail(null))` — 에러 무시 |
| `KpiSelector.tsx` | fetchKpis | `.catch(() => setKpis([]))` — 에러 무시 |
| `InsightPage.tsx` | 폴링 에러 | store에만 저장, UI toast 없음 |
| `OlapPivotPage.tsx` | 쿼리 실행 | 에러 배너 있으나 dismiss 불가 |
| `ontologyApi.ts` | 여러 호출 | catch에서 console.error만 |

**조치**:
- 모든 API 실패에 `sonner` toast 또는 에러 배너 표시
- 네트워크 에러와 비즈니스 에러 구분하여 사용자 메시지 차별화
- retry 가능한 에러는 "재시도" 버튼 제공

---

## 3. P1: 높은 우선순위 개선

### 3.1 국제화 (i18n) 리소스 완성

**현상**: i18next 인프라 구축됨 (`lib/i18n/index.ts`, `LocaleToggle.tsx`) 하지만 번역 리소스 비어있음.

**하드코딩 텍스트 예시:**
```tsx
// Nl2SqlPage.tsx
'2024-06-20 서울전자 매출은?'
'최근 3개월 처리 건수 추이'

// InsightPage.tsx
'선택 KPI', 'Impact Driver Ranking', 'Driver Detail'

// KpiSelector.tsx
'로드 중...', 'KPI 없음 — 직접 입력'
```

**조치**:
- `lib/i18n/locales/ko.json` — 한국어 리소스 작성 (모든 UI 텍스트)
- `lib/i18n/locales/en.json` — 영어 리소스 작성
- 각 컴포넌트에서 `useTranslation()` 훅으로 교체

---

### 3.2 접근성 (a11y) 개선

**주요 누락 사항:**

| 컴포넌트 | 문제 | 해결 |
|----------|------|------|
| Sidebar NavLink | `title`만 있고 `aria-label` 없음 | `aria-label={item.label}` 추가 |
| DriverRankingPanel 검색 | aria-label 없음 | `aria-label="드라이버 검색"` |
| InsightPage 정보 아이콘 | 클릭 불가능한 아이콘에 alt 없음 | `aria-hidden="true"` |
| ERDToolbar 줌 버튼 | `title`만 | `aria-label="확대"/"축소"` |
| LayerFilter 체크박스 | label 연결 | `htmlFor` + `id` 매칭 |
| DataTable 정렬 버튼 | 현재 정렬 상태 미고지 | `aria-sort` 속성 |

**조치**: WCAG 2.1 AA 기준 준수 검토 + 자동화 도구 (axe-core) 적용

---

### 3.3 성능 최적화

| 위치 | 문제 | 해결 |
|------|------|------|
| DriverRankingPanel 필터링 | `rankings.filter(...)` 매 렌더링마다 실행 | `useMemo` 래핑 |
| InsightPage selectedNode | 매 렌더링마다 lookup | `useMemo` + dependency 최소화 |
| useERDData | 200개 테이블 병렬 컬럼 요청 (N+1) | 최대 30개로 제한 + batch endpoint |
| Monaco Editor | 대형 번들 (수 MB) | `React.lazy` + dynamic import |
| Cytoscape 그래프 | 1000+ 노드에서 성능 저하 | 가상화 또는 cluster 적용 |

---

### 3.4 테스트 추가

**테스트 없는 핵심 로직:**

| 모듈 | LOC | 필요 테스트 |
|------|-----|-----------|
| `useImpactGraph.ts` | 250 | 폴링 로직, 타임아웃, 에러 복구 |
| `graphTransformer.ts` | ~80 | 그래프 데이터 변환 |
| `scoreCalculator.ts` | ~50 | 점수 계산 정확성 |
| `mermaidCodeGen.ts` | ~120 | ERD 코드 생성, FK 추론 |
| `oracleNl2sqlApi.ts` | ~175 | NDJSON 스트림 파싱, HIL 세션 |
| `fingerprintUtils.ts` | ~40 | 해시 생성 |

**조치**: Vitest 설정 + 순수 함수 단위 테스트부터 시작

---

## 4. P2: 중간 우선순위 개선

### 4.1 반응형 디자인

**문제:**
- `InsightPage`: `py-8 px-12` 고정 → 모바일에서 overflow
- `Nl2SqlPage`: `p-12` 고정 → `<640px`에서 cramped
- `Sidebar`: `w-16` 고정 → 모바일에서 햄버거 메뉴 필요
- `ProcessDesigner`: Konva 캔버스 터치 제스처 미지원

**조치**:
```tsx
// 예시: 반응형 패딩
className="py-4 px-4 sm:py-6 sm:px-8 lg:py-8 lg:px-12"
```

### 4.2 테마 시스템 일관성

**현상**: Tailwind 색상 클래스와 인라인 hex 값 혼용
```tsx
// 혼용 예시
className="bg-[#F5F5F5] text-[#333333]"  // 인라인 hex
className="bg-gray-100 text-gray-800"      // Tailwind
```

**조치**: CSS 변수 또는 Tailwind 커스텀 색상으로 통일

### 4.3 공통 컴포넌트 추출

| 패턴 | 반복 횟수 | 추출 대상 |
|------|----------|----------|
| API 에러 처리 + toast | 10+ | `useApiErrorHandler()` 훅 |
| 로딩 스피너 | 15+ | `<LoadingSpinner />` 컴포넌트 |
| Datasource 선택 | 3곳 | `<DatasourceSelect />` 공유 |
| 빈 상태 표시 | 5+ | `<EmptyState />` 이미 있으나 미사용 곳 있음 |

---

## 5. 보안 점검 결과

### ✅ 양호
- JWT 토큰 자동 갱신 (createApiClient.ts interceptor)
- `X-Tenant-Id` 헤더 자동 주입 (멀티테넌트 격리)
- `sessionStorage` 토큰 저장 (`localStorage`보다 안전)
- Oracle API 429 레이트 리밋 UI 처리

### ⚠️ 주의
- Mermaid securityLevel → `'strict'`로 수정 완료 ✅
- HIL 세션 토큰 → HMAC 서명 추가 완료 ✅
- Monaco Editor 입력값 sanitize 검토 필요
- CSRF 토큰 없음 (SPA이므로 일반적으로 불필요하나, DirectSQL 같은 위험 기능에는 검토)

---

## 6. 코드 품질 지표

| 지표 | 값 | 평가 |
|------|---|------|
| 총 소스 파일 | 263개 | — |
| Feature slices | 12개 | ✅ 체계적 |
| @ts-nocheck | 4개 파일 | 🔴 제거 필요 |
| `any` 사용 | ~15개 위치 | 🟡 타입 가드로 교체 |
| aria 속성 | 69개 | 🔴 부족 |
| 하드코딩 한국어 | 100+ 위치 | 🔴 i18n 필요 |
| 단위 테스트 | 0개 (E2E: 8개 spec) | 🔴 추가 필요 |
| TanStack Query | 12개 훅 | ✅ 캐싱 전략 양호 |
| Zustand 스토어 | 8개 | ✅ 적절한 분리 |

---

## 7. 추천 실행 계획

### Sprint 1 (즉시): P0 긴급
1. @ts-nocheck 제거 (4파일) — 0.5일
2. Silent fail 에러 처리 개선 (8건) — 1일
3. Insight API 백엔드 구현 (5개 엔드포인트) — 3일

### Sprint 2: P1 높음
4. i18n 리소스 작성 (ko.json, en.json) — 2일
5. 접근성 개선 (aria, keyboard nav) — 2일
6. 성능 최적화 (useMemo, N+1 제한) — 1일
7. Vitest 설정 + 핵심 함수 단위 테스트 — 2일

### Sprint 3: P2 중간
8. 반응형 디자인 — 3일
9. 테마 일관성 — 1일
10. 공통 컴포넌트 추출 — 1일
11. E2E 테스트 확장 — 2일

**총 예상**: ~18일 (3 스프린트)

---

## 8. KAIR 프론트엔드 대비 갭 분석

> KAIR 소스: `/media/daniel/E/AXIPIENT/projects/KAIR/robo-data-frontend/src/`
> 프레임워크: Vue.js 3 + TypeScript 5.3 + Pinia (165개 Vue 컴포넌트)

### 8.1 KAIR에 있고 Axiom에 없는 기능 (10개 카테고리)

#### P0: 엔터프라이즈 핵심

| 카테고리 | KAIR 컴포넌트 수 | 핵심 파일 | Axiom 상태 |
|----------|-----------------|----------|-----------|
| **도메인 레이어 (ObjectType)** | 15개 | `ObjectTypeModeler.vue`, `BehaviorDialog.vue` | ❌ 없음 |
| **보안/감사 관리** | 6개 | `SecurityGuardTab.vue`, `AuditLogs.vue` | ❌ Core에만 API |
| **What-if 고도화** | 12개 | `WhatIfSimulator.vue` (5단계 위자드) | 🟡 단순 버전만 |

**도메인 레이어**: KAIR의 ObjectType 시스템은 DB 스키마를 비즈니스 친화적 "도메인 객체"로 추상화하는 핵심 기능. Materialized View + Behavior(REST/JS/Python/DMN) 지원. Axiom의 온톨로지는 그래프 구조만 있고 도메인 모델링 도구가 없음.

**보안 관리**: KAIR는 사용자/역할 관리, 테이블 권한, 감사 로그를 UI에서 직접 관리. Axiom은 Core 서비스 API만 있고 프론트엔드 관리 UI 없음.

**What-if 5단계**: ① 시나리오 정의 → ② 데이터 선택 → ③ 인과 관계 발견 → ④ 모델 학습 → ⑤ 검증/시뮬레이션. Axiom은 파라미터 슬라이더 + DAG 전파만 있음.

#### P1: 데이터 관리

| 카테고리 | KAIR 컴포넌트 수 | 핵심 파일 | Axiom 상태 |
|----------|-----------------|----------|-----------|
| **데이터 수집/파이프라인** | 8개 | `UploadTab.vue`, `PipelineControlPanel.vue` | ❌ 없음 |
| **데이터 품질/관측성** | 10개 | `WatchAgent.vue` (Vue Flow), `DataQuality.vue` | 🟡 기본 Watch만 |
| **온톨로지 고도화** | 10개 | `OntologyWizard.vue`, `SchemaBasedGenerator.vue` | 🟡 브라우저만 |
| **NL2SQL 고도화** | 17개 | `SchemaCanvas.vue`, `DatabaseTree.vue` | 🟡 채팅만 |

**데이터 수집**: KAIR는 파일 드래그&드롭 업로드 + ETL 파이프라인 제어 + 실시간 진행률 UI. Axiom은 데이터소스 연결만 있고 업로드/ETL 관리 없음.

**WatchAgent**: KAIR는 Vue Flow 기반 워크플로 에디터로 SQL/조건/액션 노드를 시각적 연결. Axiom의 Watch는 규칙 목록 + 알림 피드 수준.

**NL2SQL**: KAIR는 스키마 캔버스(ERD 드래그&드롭), DB 트리 네비게이터, 관계 편집기, 상세 메타데이터 패널이 추가. Axiom은 채팅 + 결과 테이블 중심.

#### P2: 시맨틱 레이어

| 카테고리 | KAIR 컴포넌트 수 | 핵심 파일 | Axiom 상태 |
|----------|-----------------|----------|-----------|
| **데이터 리니지** | 10개 | `LineageTab.vue`, `LineageGraph.vue` | ❌ 없음 |
| **비즈니스 글로서리** | 6개 | `GlossaryTab.vue`, `TermModal.vue` | ❌ 없음 |
| **오브젝트 탐색기** | 6개 | `ObjectExplorerTab.vue`, `ObjectExplorerGraph.vue` | ❌ 없음 |

### 8.2 KAIR 아키텍처 패턴 비교

| 패턴 | KAIR | Axiom | 갭 |
|------|------|-------|---|
| 도메인 레이어 | ObjectType + Behavior | 온톨로지 그래프 | 비즈니스 로직 바인딩 없음 |
| 워크플로 에디터 | Vue Flow 기반 | 없음 (Watch는 목록) | 시각적 자동화 불가 |
| 멀티스텝 위자드 | What-if 5단계, Ontology 위자드 | 단일 뷰 | 가이드 UX 부족 |
| 스트리밍 진행률 | AnalysisProgressModal | 기본 로딩 | 세부 진행률 없음 |
| 보안 관리 | RBAC + RLS + Audit UI | API만 | 관리자 UI 없음 |
| 데이터 리니지 | 그래프 시각화 | Neo4j에 데이터만 | 시각화 없음 |

### 8.3 구현 우선순위 로드맵

#### Phase 1: 엔터프라이즈 기반 (4-6주)
| 항목 | 예상 LOC | 신규 컴포넌트 | 의존성 |
|------|---------|-------------|--------|
| 보안/감사 관리 UI | ~1,200 | 6개 | Core RBAC API |
| 도메인 레이어 모델러 | ~3,000 | 15개 | Synapse 확장 |
| What-if 5단계 위자드 | ~2,500 | 12개 | Vision DAG 엔진 |

#### Phase 2: 데이터 관리 (3-4주)
| 항목 | 예상 LOC | 신규 컴포넌트 | 의존성 |
|------|---------|-------------|--------|
| 파일 업로드 + ETL 파이프라인 | ~1,200 | 8개 | Weaver 확장 |
| 데이터 품질 대시보드 | ~1,800 | 10개 | Watch 확장 |
| 온톨로지 위자드 + 자동 생성 | ~1,800 | 10개 | Synapse |

#### Phase 3: 시맨틱 레이어 (3-4주)
| 항목 | 예상 LOC | 신규 컴포넌트 | 의존성 |
|------|---------|-------------|--------|
| 데이터 리니지 시각화 | ~1,500 | 10개 | Neo4j 리니지 |
| 비즈니스 글로서리 | ~1,500 | 6개 | Weaver 카탈로그 |
| 오브젝트 탐색기 | ~900 | 6개 | 도메인 레이어 |

**총 예상**: ~90개 컴포넌트, ~16,300 LOC, 10-14주

### 8.4 참조해야 할 KAIR 핵심 파일

| 파일 | 용도 | Axiom 대응 |
|------|------|-----------|
| `views/HomeView.vue` | 19개 탭 정의 (전체 네비게이션) | `routeConfig.tsx` |
| `components/text2sql/Text2SqlTab.vue` | NL2SQL 모드 전환 패턴 | `Nl2SqlPage.tsx` |
| `components/domain/ObjectTypeModeler.vue` | 도메인 레이어 핵심 | **신규 필요** |
| `components/whatif/WhatIfSimulator.vue` | 5단계 위자드 패턴 | `WhatIfPage.tsx` 확장 |
| `components/observability/WatchAgent.vue` | 워크플로 에디터 | **신규 필요** |
| `stores/text2sql.ts` | Pinia 스토어 패턴 | Zustand 스토어 참조 |
| `services/api.ts` | API 게이트웨이 + 스트리밍 | `createApiClient.ts` |
