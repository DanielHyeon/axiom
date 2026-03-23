import { QueryClient } from '@tanstack/react-query';
import { onQueryError, onMutationError } from './observability';

/**
 * TanStack Query 전역 클라이언트.
 * Phase 2: 글로벌 에러 핸들러 연결 (observability.ts).
 * 기본 옵션은 docs/06_data/cache-strategy.md 및 docs/04_frontend/query-client.md 참고.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5분 — 기본 fresh 유지
      gcTime: 30 * 60 * 1000, // 30분 (구 cacheTime)
      retry: 3,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      refetchOnMount: true,
    },
    mutations: {
      retry: 0,
      onError: onMutationError, // Phase 2: 글로벌 mutation 에러 수집
    },
  },
  // Phase 2: 글로벌 query 에러 수집
  queryDefaults: [{
    queryKey: [],
    defaultOptions: {
      queries: {
        meta: { onError: onQueryError },
      },
    },
  }],
});
