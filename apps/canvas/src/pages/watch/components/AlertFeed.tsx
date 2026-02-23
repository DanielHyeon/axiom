import { useAlerts } from '@/features/watch/hooks/useAlerts';
import { useWatchStore } from '@/features/watch/store/useWatchStore';
import { useMemo } from 'react';
import { Search, BellOff } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ErrorState } from '@/shared/components/ErrorState';
import { EmptyState } from '@/shared/components/EmptyState';

export function AlertFeed() {
    const { getFilteredAlerts, markAsRead, loadError, refetchAlerts } = useAlerts();
    const { filters, setSearchQuery } = useWatchStore();

    const filteredAlerts = useMemo(() => {
        return getFilteredAlerts(filters.query, filters.severity);
    }, [getFilteredAlerts, filters]);

    if (loadError) {
        return (
            <div className="flex flex-col h-full bg-card border border-border rounded-lg overflow-hidden flex-1 p-4">
                <ErrorState
                    message={`알림 목록을 불러오지 못했습니다. ${loadError.message}`}
                    onRetry={refetchAlerts}
                />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-[#161616] border border-neutral-800 rounded-lg overflow-hidden flex-1">
            <div className="p-4 border-b border-neutral-800 bg-[#1a1a1a] flex justify-between items-center">
                <h3 className="font-semibold text-neutral-200">실시간 알림 피드 ({filteredAlerts.length})</h3>
                <div className="relative w-64">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-neutral-500" />
                    <Input
                        type="text"
                        placeholder="알림 검색..."
                        className="pl-9 h-9 bg-neutral-900 border-neutral-800 text-neutral-200"
                        value={filters.query}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {filteredAlerts.length === 0 ? (
                    <EmptyState
                        icon={BellOff}
                        title="표시할 알림이 없습니다"
                        description="새 알림이 발생하거나 필터를 변경하면 여기에 표시됩니다."
                    />
                ) : (
                    filteredAlerts.map(alert => (
                        <div
                            key={alert.id}
                            onClick={() => !alert.isRead && markAsRead(alert.id)}
                            className={`p-4 rounded-lg border transition-all ${!alert.isRead
                                ? 'bg-[#1e1e1e] border-neutral-700 cursor-pointer hover:border-neutral-600'
                                : 'bg-neutral-900 border-neutral-800/50 opacity-70'
                                }`}
                        >
                            <div className="flex justify-between items-start mb-2">
                                <div className="flex items-center gap-2">
                                    {!alert.isRead && <span className="w-2 h-2 rounded-full bg-blue-500" />}
                                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                                        alert.severity === 'warning' ? 'bg-amber-500/20 text-amber-400' :
                                            'bg-blue-500/20 text-blue-400'
                                        }`}>
                                        {alert.severity.toUpperCase()}
                                    </span>
                                </div>
                                <span className="text-xs text-neutral-500">
                                    {new Date(alert.timestamp).toLocaleString()}
                                </span>
                            </div>
                            <h4 className={`text-sm font-semibold mb-1 ${!alert.isRead ? 'text-neutral-200' : 'text-neutral-400'}`}>
                                {alert.title}
                            </h4>
                            <p className="text-sm text-neutral-400">
                                {alert.description}
                            </p>
                            {alert.sourceNodeId && (
                                <div className="mt-3 text-xs flex items-center gap-1.5 text-neutral-500 font-mono bg-neutral-950 p-1.5 rounded w-fit border border-neutral-800/50">
                                    관련 노드: <span className="text-neutral-300">{alert.sourceNodeId}</span>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
