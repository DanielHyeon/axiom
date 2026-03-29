/**
 * 케이스 상세 조회 훅 — GET /api/v1/cases/:id
 * CaseDetailPage에서 사용. 개별 케이스의 전체 필드를 가져온다.
 */
import { useQuery } from '@tanstack/react-query';
import { getCaseDetail } from '@/lib/api/casesApi';
import type { Case } from './useCases';

export function useCaseDetail(caseId: string) {
  return useQuery({
    queryKey: ['cases', 'detail', caseId],
    queryFn: async (): Promise<Case> => {
      const res = await getCaseDetail(caseId);
      return {
        id: res.id,
        title: res.title,
        status: res.status as Case['status'],
        priority: res.priority as Case['priority'],
        assignee: res.assignee ?? undefined,
        createdAt: res.createdAt,
        updatedAt: res.updatedAt ?? undefined,
        dueDate: res.dueDate ?? undefined,
      };
    },
    enabled: !!caseId,
  });
}
