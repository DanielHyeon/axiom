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
