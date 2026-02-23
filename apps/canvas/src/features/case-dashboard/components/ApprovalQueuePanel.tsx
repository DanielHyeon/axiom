import { useApprovalQueue, useApproveHitl, useReworkWorkitem } from '../hooks/useApprovalQueue';

export function ApprovalQueuePanel() {
  const { data: items = [], isLoading, error } = useApprovalQueue(20);
  const approveHitl = useApproveHitl();
  const rework = useReworkWorkitem();

  if (isLoading) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
        <h2 className="mb-4 text-lg font-semibold text-white">검토 대기</h2>
        <div className="space-y-3 animate-pulse">
          <div className="h-12 bg-neutral-800 rounded w-full" />
          <div className="h-12 bg-neutral-800 rounded w-full" />
          <div className="h-12 bg-neutral-800 rounded w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-900/50 bg-red-900/20 p-4">
        <h2 className="mb-2 text-lg font-semibold text-white">검토 대기</h2>
        <p className="text-sm text-red-200">데이터를 불러오는 중 오류가 발생했습니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <h2 className="mb-4 text-lg font-semibold text-white">검토 대기</h2>
      <div className="grid gap-3">
        {items.map((item) => (
          <div
            key={item.workitem_id}
            className="rounded-lg border border-neutral-800 bg-neutral-950 p-3"
          >
            <div className="font-medium text-white">
              {item.activity_name ?? item.workitem_id}
            </div>
            <div className="mt-1 flex items-center gap-2 text-xs text-neutral-400">
              <span>{item.status}</span>
              {item.proc_inst_id && (
                <>
                  <span>·</span>
                  <span>{item.proc_inst_id}</span>
                </>
              )}
            </div>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() =>
                  approveHitl.mutate({
                    workitem_id: item.workitem_id,
                    approved: true,
                  })
                }
                disabled={approveHitl.isPending}
                className="rounded bg-emerald-600 px-2 py-1 text-xs text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                승인
              </button>
              <button
                type="button"
                onClick={() =>
                  rework.mutate({
                    workitem_id: item.workitem_id,
                    reason: '검토 반려',
                  })
                }
                disabled={rework.isPending}
                className="rounded bg-neutral-600 px-2 py-1 text-xs text-white hover:bg-neutral-500 disabled:opacity-50"
              >
                반려
              </button>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-sm text-neutral-500">승인/반려 대기 항목이 없습니다.</p>
        )}
      </div>
    </div>
  );
}
