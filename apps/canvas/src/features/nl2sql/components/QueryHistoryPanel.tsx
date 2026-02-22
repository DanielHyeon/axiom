import { getHistory, type HistoryItem } from '../api/oracleNl2sqlApi';
import { useQuery } from '@tanstack/react-query';

interface QueryHistoryPanelProps {
  datasourceId?: string;
  onSelect?: (item: HistoryItem) => void;
}

export function QueryHistoryPanel({ datasourceId, onSelect }: QueryHistoryPanelProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['nl2sql', 'history', datasourceId, 1, 20],
    queryFn: () => getHistory({ datasource_id: datasourceId, page: 1, page_size: 20 }),
    staleTime: 60 * 1000,
  });

  const history = data?.data?.history ?? [];
  const pagination = data?.data?.pagination;

  if (isLoading) {
    return (
      <div className="rounded border border-neutral-800 bg-neutral-900/50 p-3">
        <h3 className="text-sm font-semibold text-white mb-2">최근 질의</h3>
        <div className="space-y-2 animate-pulse">
          <div className="h-12 bg-neutral-800 rounded" />
          <div className="h-12 bg-neutral-800 rounded" />
          <div className="h-12 bg-neutral-800 rounded" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded border border-neutral-800 bg-neutral-900/50 p-3">
        <h3 className="text-sm font-semibold text-white mb-2">최근 질의</h3>
        <p className="text-xs text-neutral-500">이력을 불러올 수 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded border border-neutral-800 bg-neutral-900/50 p-3">
      <h3 className="text-sm font-semibold text-white mb-2">최근 질의</h3>
      <ul className="space-y-2 max-h-64 overflow-auto">
        {history.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onSelect?.(item)}
              className="w-full text-left rounded border border-neutral-800 bg-neutral-950 px-2 py-2 hover:bg-neutral-800/50 transition text-sm"
            >
              <span className="line-clamp-2 text-neutral-300">{item.question}</span>
              <span className="mt-1 block text-xs text-neutral-500">
                {item.status === 'success' ? '성공' : '오류'} · {item.row_count ?? '—'}행
                {item.created_at && ` · ${new Date(item.created_at).toLocaleDateString('ko-KR')}`}
              </span>
            </button>
          </li>
        ))}
        {history.length === 0 && (
          <li className="text-sm text-neutral-500">최근 질의가 없습니다.</li>
        )}
      </ul>
      {pagination && pagination.total_count > 0 && (
        <p className="mt-2 text-xs text-neutral-500">
          총 {pagination.total_count}건
        </p>
      )}
    </div>
  );
}
