import { useQuery } from '@tanstack/react-query';
import { listCaseActivities } from '@/lib/api/casesApi';

export interface TimelineItem {
  id: string;
  time: string;
  text: string;
}

export function useCaseActivities(limit?: number) {
  return useQuery({
    queryKey: ['cases', 'activities', limit],
    queryFn: async (): Promise<TimelineItem[]> => {
      const res = await listCaseActivities(limit ?? 20);
      return (res.items ?? []).map((a) => ({ id: a.id, time: a.time, text: a.text }));
    },
  });
}
