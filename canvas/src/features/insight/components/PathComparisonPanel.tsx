// features/insight/components/PathComparisonPanel.tsx
// Top 3 impact path comparison with checkbox toggles

import { cn } from '@/lib/utils';
import { Route } from 'lucide-react';
import type { ImpactPath } from '../types/insight';

interface PathComparisonPanelProps {
 paths: ImpactPath[];
 nodeLabels?: Record<string, string>;
 highlightedPaths: string[];
 onTogglePath: (pathId: string) => void;
}

const PATH_CHECKED_CLS = [
 'bg-rose-500',
 'bg-primary',
 'bg-violet-400',
] as const;

const PATH_DOT_CLS = [
 'bg-rose-500/20 text-rose-400',
 'bg-primary/20 text-primary',
 'bg-violet-400/20 text-violet-400',
] as const;

function resolveLabel(nodeId: string, nodeLabels?: Record<string, string>): string {
 if (nodeLabels?.[nodeId]) return nodeLabels[nodeId];
 // Fallback: strip prefix (e.g. "col:public.orders.status" → "orders.status")
 const parts = nodeId.split(':');
 if (parts.length > 1) return parts.slice(1).join(':').replace(/^[^.]+\./, '');
 return nodeId;
}

export function PathComparisonPanel({
 paths,
 nodeLabels,
 highlightedPaths,
 onTogglePath,
}: PathComparisonPanelProps) {
 const topPaths = [...paths]
 .sort((a, b) => (b.strength ?? 0) - (a.strength ?? 0))
 .slice(0, 3);

 if (topPaths.length === 0) return null;

 return (
 <div className="rounded-lg border border-border bg-card/50 p-3">
 <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground mb-2">
 <Route className="h-3 w-3" />
 영향 경로 Top {topPaths.length}
 </div>

 <div className="space-y-1.5">
 {topPaths.map((path, idx) => {
 const isActive = highlightedPaths.includes(path.path_id);
 const checkedCls = PATH_CHECKED_CLS[idx] ?? 'bg-background0';
 const dotCls = PATH_DOT_CLS[idx] ?? 'bg-background0/20 text-muted-foreground';
 const labels = path.nodes.map((id) => resolveLabel(id, nodeLabels));

 return (
 <label
 key={path.path_id}
 className={cn(
 'flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer transition-colors',
 isActive ? 'bg-muted/60' : 'hover:bg-muted/30',
 )}
 >
 <input
 type="checkbox"
 checked={isActive}
 onChange={() => onTogglePath(path.path_id)}
 className="sr-only"
 />
 <div
 className={cn(
 'w-3 h-3 rounded-sm border-2 flex items-center justify-center shrink-0 transition-colors',
 isActive ? cn('border-transparent', checkedCls) : 'border-border',
 )}
 >
 {isActive && (
 <svg className="w-2 h-2 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={4}>
 <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
 </svg>
 )}
 </div>

 <div className="flex-1 min-w-0">
 <div className={cn('text-[10px] truncate', dotCls.split(' ')[1] ?? 'text-foreground/80')}>
 {labels.join(' → ')}
 </div>
 </div>

 <div className="shrink-0 text-[10px] text-muted-foreground">
 {Math.round((path.strength ?? 0) * 100)}%
 </div>
 </label>
 );
 })}
 </div>
 </div>
 );
}
