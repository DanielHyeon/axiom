import type { Alert } from '@/features/watch/types/watch';

interface EventTimelineProps {
    events: Alert[];
    onMarkAsRead?: (id: string) => void;
}

export function EventTimeline({ events, onMarkAsRead }: EventTimelineProps) {
    const sorted = [...events].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

    return (
        <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px bg-neutral-700" />
            <ul className="space-y-0">
                {sorted.map((alert) => (
                    <li key={alert.id} className="relative flex gap-4 pl-10 pb-6 last:pb-0">
                        <span
                            className={`absolute left-2.5 top-1.5 w-3 h-3 rounded-full border-2 border-[#1a1a1a] ${
                                alert.severity === 'critical' ? 'bg-red-500' :
                                alert.severity === 'warning' ? 'bg-amber-500' : 'bg-blue-500'
                            }`}
                        />
                        <div
                            role={onMarkAsRead && !alert.isRead ? 'button' : undefined}
                            onClick={onMarkAsRead && !alert.isRead ? () => onMarkAsRead(alert.id) : undefined}
                            className={`flex-1 min-w-0 p-3 rounded-lg border ${
                                !alert.isRead
                                    ? 'bg-[#1e1e1e] border-neutral-700 cursor-pointer hover:border-neutral-600'
                                    : 'bg-neutral-900/50 border-neutral-800 opacity-80'
                            }`}
                        >
                            <div className="flex justify-between items-start gap-2">
                                <span className="text-xs text-neutral-500 shrink-0">
                                    {new Date(alert.timestamp).toLocaleString()}
                                </span>
                                <span className={`text-xs font-medium px-2 py-0.5 rounded shrink-0 ${
                                    alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                                    alert.severity === 'warning' ? 'bg-amber-500/20 text-amber-400' : 'bg-blue-500/20 text-blue-400'
                                }`}>
                                    {alert.severity.toUpperCase()}
                                </span>
                            </div>
                            <h4 className="text-sm font-semibold text-neutral-200 mt-1">{alert.title}</h4>
                            <p className="text-sm text-neutral-400 mt-0.5">{alert.description}</p>
                            {alert.sourceNodeId && (
                                <p className="text-xs text-neutral-500 mt-2 font-mono">{alert.sourceNodeId}</p>
                            )}
                        </div>
                    </li>
                ))}
            </ul>
            {sorted.length === 0 && (
                <div className="py-8 text-center text-neutral-500 text-sm">이벤트가 없습니다.</div>
            )}
        </div>
    );
}
