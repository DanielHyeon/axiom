# TanStack Query 전역 옵션

<!-- 구현: apps/canvas/src/lib/queryClient.ts -->

## 개요

Canvas 앱의 TanStack Query 전역 설정은 `src/lib/queryClient.ts`에서 정의하며, `main.tsx`에서 `QueryClientProvider`로 주입한다.  
캐시 정책·무효화 패턴은 [06_data/cache-strategy.md](../06_data/cache-strategy.md) 참고.

---

## 1. 전역 기본값 (defaultOptions)

### 1.1 Queries

| 옵션 | 값 | 설명 |
|------|-----|------|
| **staleTime** | 5분 | 이 시간까지는 데이터를 fresh로 간주하고 refetch하지 않음. 개별 쿼리에서 오버라이드 가능. |
| **gcTime** | 30분 | 미사용 캐시가 메모리에서 제거되기까지 유지 시간. |
| **retry** | 3 | 실패 시 최대 3회 재시도. |
| **retryDelay** | 지수 백오프 (1s, 2s, 4s … 최대 30s) | 재시도 간격. |
| **refetchOnWindowFocus** | true | 창 포커스 시 stale 쿼리 자동 refetch. |
| **refetchOnReconnect** | true | 네트워크 재연결 시 refetch. |
| **refetchOnMount** | true | 컴포넌트 마운트 시 stale이면 refetch. |

### 1.2 Mutations

| 옵션 | 값 | 설명 |
|------|-----|------|
| **retry** | 0 | 전역 기본은 재시도 없음. 특정 mutation에서만 `useMutation({ retry: 1 })` 등으로 지정. |

Mutation 에러는 전역 `onError`로 처리하지 않고, 각 `useMutation`의 `onError` 또는 컴포넌트에서 `mutate(..., { onError })`로 처리한다. 토스트·스낵바 등은 mutation 호출부에서 처리.

---

## 2. 쿼리별 오버라이드

데이터 유형별 권장 staleTime/gcTime은 [cache-strategy.md §1.1](../06_data/cache-strategy.md) 표 참고.  
예: 케이스 목록은 `staleTime: 60 * 1000`, 알림 피드는 `staleTime: 0` 등으로 개별 `useQuery`에서 설정.

---

## 3. 참고

- [06_data/cache-strategy.md](../06_data/cache-strategy.md) — 캐시 정책, 무효화 패턴, 낙관적 업데이트
- [ADR-004 TanStack Query](../../99_decisions/ADR-004-tanstack-query.md)
