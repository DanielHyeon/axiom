import { QueryClient } from '@tanstack/react-query';

/**
 * TanStack Query 전역 클라이언트.
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
      retry: 0, // mutation은 기본 재시도 없음. 필요 시 useMutation 옵션으로 지정
    },
  },
});
