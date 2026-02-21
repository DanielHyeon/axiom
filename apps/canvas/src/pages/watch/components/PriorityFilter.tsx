import { useWatchStore } from '@/features/watch/store/useWatchStore';
import type { AlertSeverity } from '@/features/watch/types/watch';

const SEVERITY_CONFIG: { id: AlertSeverity; label: string; bg: string; text: string; border: string }[] = [
    { id: 'critical', label: 'Critical', bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-900/50' },
    { id: 'warning', label: 'Warning', bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-900/50' },
    { id: 'info', label: 'Info', bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-900/50' }
];

export function PriorityFilter() {
    const { filters, toggleSeverity } = useWatchStore();

    return (
        <div className="flex gap-2">
            {SEVERITY_CONFIG.map(config => {
                const isActive = filters.severity.has(config.id);
                return (
                    <button
                        key={config.id}
                        onClick={() => toggleSeverity(config.id)}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${isActive
                            ? `${config.bg} ${config.text} ${config.border}`
                            : 'bg-neutral-900 text-neutral-500 border-neutral-800 hover:border-neutral-700 hover:text-neutral-400'
                            }`}
                    >
                        {config.label}
                    </button>
                );
            })}
        </div>
    );
}
