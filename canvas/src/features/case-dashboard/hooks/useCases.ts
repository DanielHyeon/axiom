/**
 * 케이스 목록 조회 훅 — TanStack Query 기반.
 * 서버 측 status/search/pagination 필터를 지원한다.
 */
import { useQuery } from '@tanstack/react-query';
import { listCases } from '@/lib/api/casesApi';

export interface Case {
  id: string;
  title: string;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED';
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  assignee?: string;
  createdAt: string;
  updatedAt?: string;
  dueDate?: string;
}

/** API 응답을 Case 인터페이스로 정규화 */
function mapItemToCase(item: {
  id: string;
  title: string;
  status: string;
  priority: string;
  assignee?: string | null;
  createdAt: string;
  updatedAt?: string | null;
  dueDate?: string | null;
}): Case {
  return {
    id: item.id,
    title: item.title,
    status: item.status as Case['status'],
    priority: item.priority as Case['priority'],
    assignee: item.assignee ?? undefined,
    createdAt: item.createdAt,
    updatedAt: item.updatedAt ?? undefined,
    dueDate: item.dueDate ?? undefined,
  };
}

/** 케이스 목록 + 총 개수 반환 */
export function useCases(params?: {
  status?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ['cases', params?.status, params?.search, params?.limit, params?.offset],
    queryFn: async () => {
      const res = await listCases({
        status: params?.status,
        search: params?.search,
        limit: params?.limit ?? 100,
        offset: params?.offset ?? 0,
      });
      return {
        items: (res.items ?? []).map(mapItemToCase),
        total: res.total ?? 0,
      };
    },
  });
}
