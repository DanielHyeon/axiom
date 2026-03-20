import { useQuery } from '@tanstack/react-query';
import { listCases } from '@/lib/api/casesApi';

export interface Case {
  id: string;
  title: string;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED';
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  createdAt: string;
  dueDate?: string;
}

function mapItemToCase(item: {
  id: string;
  title: string;
  status: string;
  priority: string;
  createdAt: string;
  dueDate?: string | null;
}): Case {
  return {
    id: item.id,
    title: item.title,
    status: item.status as Case['status'],
    priority: item.priority as Case['priority'],
    createdAt: item.createdAt,
    dueDate: item.dueDate ?? undefined,
  };
}

export function useCases(params?: { status?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['cases', params?.status, params?.limit, params?.offset],
    queryFn: async (): Promise<Case[]> => {
      const res = await listCases({
        status: params?.status,
        limit: params?.limit ?? 100,
        offset: params?.offset ?? 0,
      });
      return (res.items ?? []).map(mapItemToCase);
    },
  });
}
