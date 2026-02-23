import { useApprovalQueue, useApproveHitl, useReworkWorkitem } from '../hooks/useApprovalQueue';
import { CheckCircle2, XCircle, FileCheck } from 'lucide-react';

export function ApprovalQueuePanel() {
  const { data: items = [], isLoading, error } = useApprovalQueue(20);
  const approveHitl = useApproveHitl();
  const rework = useReworkWorkitem();

  if (isLoading) {
    return (
      <div className="glass-card rounded-xl p-5">
        <h2 className="mb-4 text-lg font-semibold text-foreground">검토 대기</h2>
        <div className="space-y-3 animate-pulse">
          <div className="h-14 rounded-lg bg-muted/30" />
          <div className="h-14 rounded-lg bg-muted/30" />
          <div className="h-14 rounded-lg bg-muted/30" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card rounded-xl border-destructive/20 p-5">
        <h2 className="mb-2 text-lg font-semibold text-foreground">검토 대기</h2>
        <p className="text-sm text-destructive">데이터를 불러오는 중 오류가 발생했습니다.</p>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-xl p-5">
      <h2 className="mb-4 text-lg font-semibold text-foreground">검토 대기</h2>
      <div className="grid gap-3">
        {items.map((item) => (
          <div
            key={item.workitem_id}
            className="rounded-lg bg-muted/30 border border-border/25 p-4"
          >
            <div className="font-medium text-foreground">
              {item.activity_name ?? item.workitem_id}
            </div>
            <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center rounded-full bg-warning/15 px-2 py-0.5 text-warning text-[11px] font-medium">
                {item.status}
              </span>
              {item.proc_inst_id && (
                <>
                  <span>·</span>
                  <span>{item.proc_inst_id}</span>
                </>
              )}
            </div>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() =>
                  approveHitl.mutate({
                    workitem_id: item.workitem_id,
                    approved: true,
                  })
                }
                disabled={approveHitl.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-success/90 px-3 py-1.5 text-xs font-medium text-white transition-all duration-200 hover:bg-success hover:shadow-sm hover:shadow-success/25 disabled:opacity-50"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
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
                className="inline-flex items-center gap-1.5 rounded-lg border border-border/30 bg-muted/40 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all duration-200 hover:text-foreground hover:bg-muted/60 disabled:opacity-50"
              >
                <XCircle className="h-3.5 w-3.5" />
                반려
              </button>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <div className="flex flex-col items-center py-8 text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted/50">
              <FileCheck className="h-5 w-5 text-muted-foreground/50" />
            </div>
            <p className="text-sm text-muted-foreground">승인/반려 대기 항목이 없습니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}
