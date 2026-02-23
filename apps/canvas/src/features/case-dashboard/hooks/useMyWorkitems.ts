import { useQuery } from '@tanstack/react-query';
import { listWorkitems } from '@/lib/api/processApi';
import type { WorkitemListItem } from '@/lib/api/processApi';

export function useMyWorkitems(limit = 20) {
  return useQuery({
    queryKey: ['workitems', 'my', limit],
    queryFn: async (): Promise<WorkitemListItem[]> => {
      const res = await listWorkitems({ assignee: 'me', limit });
      return res.items ?? [];
    },
  });
}
