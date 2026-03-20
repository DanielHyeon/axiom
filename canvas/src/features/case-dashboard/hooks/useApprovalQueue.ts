import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listWorkitems, approveHitl, reworkWorkitem } from '@/lib/api/processApi';
import type { WorkitemListItem } from '@/lib/api/processApi';

export function useApprovalQueue(limit = 20) {
  return useQuery({
    queryKey: ['workitems', 'approval', limit],
    queryFn: async (): Promise<WorkitemListItem[]> => {
      const res = await listWorkitems({ status: 'SUBMITTED', limit });
      return res.items ?? [];
    },
  });
}

export function useApproveHitl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { workitem_id: string; approved: boolean; modifications?: { feedback?: string } }) =>
      approveHitl(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workitems', 'approval'] });
      queryClient.invalidateQueries({ queryKey: ['workitems', 'my'] });
    },
  });
}

export function useReworkWorkitem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { workitem_id: string; reason: string; revert_to_activity_id?: string | null }) =>
      reworkWorkitem(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workitems', 'approval'] });
      queryClient.invalidateQueries({ queryKey: ['workitems', 'my'] });
    },
  });
}
