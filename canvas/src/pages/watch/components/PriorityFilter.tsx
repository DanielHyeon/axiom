import { useWatchStore } from '@/features/watch/store/useWatchStore';
import type { AlertSeverity } from '@/features/watch/types/watch';

const SEVERITY_CONFIG: { id: AlertSeverity; label: string; bg: string; text: string; border: string }[] = [
 { id: 'critical', label: 'Critical', bg: 'bg-destructive/20', text: 'text-destructive', border: 'border-red-900/50' },
 { id: 'warning', label: 'Warning', bg: 'bg-warning/20', text: 'text-warning', border: 'border-amber-900/50' },
 { id: 'info', label: 'Info', bg: 'bg-primary/20', text: 'text-primary', border: 'border-blue-900/50' }
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
 : 'bg-card text-foreground0 border-border hover:border-border hover:text-muted-foreground'
 }`}
 >
 {config.label}
 </button>
 );
 })}
 </div>
 );
}
