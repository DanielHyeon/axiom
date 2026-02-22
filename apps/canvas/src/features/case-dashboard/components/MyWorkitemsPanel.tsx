import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import type { Case } from '../hooks/useCases';

interface MyWorkitemsPanelProps {
  cases: Case[];
  isLoading?: boolean;
  error?: Error | null;
}

const statusLabel: Record<Case['status'], string> = {
  PENDING: '대기',
  IN_PROGRESS: '진행 중',
  COMPLETED: '완료',
  REJECTED: '반려',
};

export function MyWorkitemsPanel({ cases, isLoading, error }: MyWorkitemsPanelProps) {
  if (isLoading) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
        <h2 className="text-lg font-semibold text-white mb-4">내 할당 업무</h2>
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
        <p className="text-sm text-red-200">데이터를 불러오는 중 오류가 발생했습니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <h2 className="text-lg font-semibold text-white mb-4">내 할당 업무</h2>
      <div className="grid gap-3">
        {cases.map((c) => (
          <Link
            key={c.id}
            to={ROUTES.CASES.DETAIL(c.id)}
            className="block p-3 rounded-lg border border-neutral-800 bg-neutral-950 hover:bg-neutral-800/50 transition-colors"
          >
            <div className="font-medium text-white">{c.title}</div>
            <div className="mt-1 flex items-center gap-2 text-xs text-neutral-400">
              <span>{statusLabel[c.status]}</span>
              <span>·</span>
              <span>{c.priority}</span>
            </div>
          </Link>
        ))}
        {cases.length === 0 && (
          <p className="text-sm text-neutral-500">할당된 케이스가 없습니다.</p>
        )}
      </div>
    </div>
  );
}
