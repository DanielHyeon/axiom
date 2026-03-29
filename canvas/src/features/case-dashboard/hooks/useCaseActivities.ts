/**
 * 케이스 활동 타임라인 훅 — GET /api/v1/cases/activities
 * case_id를 전달하면 해당 케이스의 활동만 필터링한다.
 */
import { useQuery } from '@tanstack/react-query';
import { listCaseActivities } from '@/lib/api/casesApi';

export interface TimelineItem {
  id: string;
  time: string;
  text: string;
}

export function useCaseActivities(params?: { caseId?: string; limit?: number }) {
  return useQuery({
    queryKey: ['cases', 'activities', params?.caseId, params?.limit],
    queryFn: async (): Promise<TimelineItem[]> => {
      const res = await listCaseActivities({
        caseId: params?.caseId,
        limit: params?.limit ?? 20,
      });
      return (res.items ?? []).map((a) => ({ id: a.id, time: a.time, text: a.text }));
    },
    enabled: params?.caseId ? !!params.caseId : true,
  });
}
