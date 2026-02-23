import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { useMyWorkitems } from '../hooks/useMyWorkitems';

export function MyWorkitemsPanel() {
  const { data: items = [], isLoading, error } = useMyWorkitems(20);

  if (isLoading) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
        <h2 className="mb-4 text-lg font-semibold text-white">내 할당 업무</h2>
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
        <h2 className="mb-2 text-lg font-semibold text-white">내 할당 업무</h2>
        <p className="text-sm text-red-200">데이터를 불러오는 중 오류가 발생했습니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <h2 className="mb-4 text-lg font-semibold text-white">내 할당 업무</h2>
      <div className="grid gap-3">
        {items.map((item) => (
          <Link
            key={item.workitem_id}
            to={item.proc_inst_id ? ROUTES.CASES.DETAIL(item.proc_inst_id) : '#'}
            className="block rounded-lg border border-neutral-800 bg-neutral-950 p-3 transition-colors hover:bg-neutral-800/50"
          >
            <div className="font-medium text-white">
              {item.activity_name ?? item.workitem_id}
            </div>
            <div className="mt-1 flex items-center gap-2 text-xs text-neutral-400">
              <span>{item.status}</span>
              <span>·</span>
              <span>{item.activity_type ?? 'task'}</span>
            </div>
          </Link>
        ))}
        {items.length === 0 && (
          <p className="text-sm text-neutral-500">할당된 워크아이템이 없습니다.</p>
        )}
      </div>
    </div>
  );
}
