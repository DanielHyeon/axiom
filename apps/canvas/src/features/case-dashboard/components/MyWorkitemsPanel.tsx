import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { useMyWorkitems } from '../hooks/useMyWorkitems';
import { ClipboardList } from 'lucide-react';

export function MyWorkitemsPanel() {
  const { data: items = [], isLoading, error } = useMyWorkitems(20);

  if (isLoading) {
    return (
      <div className="glass-card rounded-xl p-5">
        <h2 className="mb-4 text-lg font-semibold text-foreground">내 할당 업무</h2>
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
        <h2 className="mb-2 text-lg font-semibold text-foreground">내 할당 업무</h2>
        <p className="text-sm text-destructive">데이터를 불러오는 중 오류가 발생했습니다.</p>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-xl p-5">
      <h2 className="mb-4 text-lg font-semibold text-foreground">내 할당 업무</h2>
      <div className="grid gap-3">
        {items.map((item) => (
          <Link
            key={item.workitem_id}
            to={item.proc_inst_id ? ROUTES.CASES.DETAIL(item.proc_inst_id) : '#'}
            className="block rounded-lg bg-muted/30 border border-border/25 p-4 transition-all duration-200 hover:bg-muted/50"
          >
            <div className="font-medium text-foreground">
              {item.activity_name ?? item.workitem_id}
            </div>
            <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center rounded-full bg-primary/15 px-2 py-0.5 text-primary text-[11px] font-medium">
                {item.status}
              </span>
              <span>·</span>
              <span>{item.activity_type ?? 'task'}</span>
            </div>
          </Link>
        ))}
        {items.length === 0 && (
          <div className="flex flex-col items-center py-8 text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted/50">
              <ClipboardList className="h-5 w-5 text-muted-foreground/50" />
            </div>
            <p className="text-sm text-muted-foreground">할당된 워크아이템이 없습니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}
