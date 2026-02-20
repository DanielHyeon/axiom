# ADR-005: React Router v6 라우팅 선택

## 상태

Accepted (수락됨)

## 배경

Canvas의 라우팅 솔루션을 선택해야 했다. K-AIR는 Vue Router 4를 사용했으며, 다음과 같은 라우팅 요구사항이 있었다.

### 요구사항

1. 중첩 라우트: `/cases/:caseId/documents/:docId/review`
2. 라우트별 코드 분할 (lazy loading)
3. 인증 가드 (보호 라우트)
4. URL 기반 상태 (필터, 페이지네이션)
5. 레이아웃 중첩 (AuthLayout vs DashboardLayout)
6. 프로그래매틱 네비게이션

## 고려한 옵션

### 옵션 1: React Router v6

- React 생태계 표준
- 중첩 라우트, Outlet, 레이아웃 라우트
- createBrowserRouter (Data API)
- loader/action 패턴 (선택적)

### 옵션 2: TanStack Router

- 타입 안전 라우팅 (라우트 경로까지 타입 체크)
- 빌트인 검색 파라미터 관리
- 상대적으로 신규 (생태계 소규모)
- 러닝 커브 높음

### 옵션 3: Next.js App Router

- 파일 기반 라우팅
- SSR/SSG 지원
- Next.js 프레임워크 종속
- Canvas는 순수 SPA -> SSR 이점 제한

## 선택한 결정

**옵션 1: React Router v6 (createBrowserRouter API)**

## 근거

| 기준 | React Router v6 | TanStack Router | Next.js | 비중 |
|------|-----------------|----------------|---------|------|
| **성숙도/안정성** | 최고 | 중간 | 높음 | 30% |
| **중첩 라우트** | 네이티브 | 네이티브 | 파일 기반 | 20% |
| **타입 안전성** | 중간 | 최고 | 중간 | 15% |
| **코드 분할** | React.lazy | 빌트인 | 자동 | 15% |
| **채용/학습** | 최고 (사실상 표준) | 낮음 | 높음 | 20% |

### 핵심 결정 요인

1. **사실상 표준**: React Router는 React 생태계의 de facto 라우팅 솔루션. 대부분의 React 개발자가 숙지
2. **createBrowserRouter**: 데이터 로더, 에러 바운더리, 중첩 레이아웃을 선언적으로 정의
3. **K-AIR Vue Router와의 유사성**: Vue Router 4와 React Router v6의 중첩 라우트 개념이 유사하여 전환 용이
4. **TanStack Router 리스크**: 타입 안전성은 매력적이나, 아직 메이저 업데이트가 활발하여 안정성 우려

## K-AIR Vue Router -> Canvas React Router 전환 패턴

```
// K-AIR (Vue Router 4)
{
  path: '/cases/:id',
  component: () => import('./CaseDetail.vue'),
  meta: { requiresAuth: true },
  children: [
    { path: 'documents', component: () => import('./DocumentList.vue') }
  ]
}

// Canvas (React Router v6)
{
  path: 'cases/:caseId',
  element: <Suspense><CaseDetailPage /></Suspense>,
  // requiresAuth -> AuthGuard 컴포넌트로 대체
  children: [
    { path: 'documents', element: <Suspense><DocumentListPage /></Suspense> }
  ]
}
```

## 부정적 결과

- URL 파라미터의 타입 안전성은 런타임 검증에 의존 (TanStack Router 대비)
- loader/action 패턴은 TanStack Query와 역할 중복 가능 -> Canvas에서는 사용하지 않기로 결정
- React Router v7 (Remix 통합) 전환 시 마이그레이션 비용 발생 가능

## 긍정적 결과

- 팀 온보딩 비용 최소
- 안정적인 생태계 지원
- 레이아웃 중첩으로 AuthLayout/DashboardLayout 깔끔 분리

## 재평가 조건

- TanStack Router가 v2 안정 릴리스되고 생태계가 성숙해지면 검토
- React Router v7 출시 시 마이그레이션 평가
- URL 기반 상태 관리가 복잡해져 타입 안전 라우팅이 필수적일 때

---

## 변경 이력

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2026-02-19 | Axiom Team | 초기 작성 |
