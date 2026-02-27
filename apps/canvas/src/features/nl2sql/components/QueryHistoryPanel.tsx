import { getHistory, type HistoryItem } from '../api/oracleNl2sqlApi';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';

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

  if (isLoading) {
    return (
      <div className="py-2 space-y-1 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div key={i} className="py-3 px-6">
            <div className="h-4 bg-[#E5E5E5] rounded w-3/4" />
            <div className="h-3 bg-[#E5E5E5] rounded w-1/2 mt-2" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-center">
        <p className="text-xs text-[#999] font-[IBM_Plex_Mono]">이력을 불러올 수 없습니다.</p>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-xs text-[#999] font-[IBM_Plex_Mono]">최근 질의가 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col py-2">
      {history.map((item, idx) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect?.(item)}
          className={cn(
            'w-full text-left py-3 px-6 transition-colors hover:bg-[#F5F5F5]',
            idx === 0 && 'bg-[#F5F5F5]'
          )}
        >
          <span
            className={cn(
              'block text-[13px] font-[Sora] line-clamp-2',
              idx === 0 ? 'text-black font-medium' : 'text-[#5E5E5E]'
            )}
          >
            {item.question}
          </span>
          <span className="mt-1.5 flex items-center gap-2 text-[11px] text-[#999] font-[IBM_Plex_Mono]">
            {item.created_at && (
              <span>{formatTimeAgo(item.created_at)}</span>
            )}
            {item.row_count != null && (
              <>
                <span>·</span>
                <span>{item.row_count} rows</span>
              </>
            )}
          </span>
        </button>
      ))}
    </div>
  );
}

function formatTimeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'Yesterday';
  return `${days} days ago`;
}
