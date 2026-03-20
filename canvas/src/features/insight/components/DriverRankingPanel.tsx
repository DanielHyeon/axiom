// features/insight/components/DriverRankingPanel.tsx
// Sorted list of DRIVER + DIMENSION nodes with search, hover highlight, and click-to-detail

import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { TrendingUp, Layers, Columns3, Search } from 'lucide-react';
import type { GraphData, DriverRankItem } from '../types/insight';
import { deriveDriverRankings, formatScoreRaw, scoreColor, scoreBgColor } from '../utils/scoreCalculator';

interface DriverRankingPanelProps {
 graphData: GraphData | null;
 impactEvidence: Record<string, unknown[]> | null;
 selectedDriverId: string | null;
 onSelectDriver: (driverId: string) => void;
 onHoverDriver?: (driverId: string | null) => void;
}

const TYPE_ICON = {
 DRIVER: TrendingUp,
 DIMENSION: Layers,
} as const;

const TYPE_COLOR = {
 DRIVER: 'text-orange-400',
 DIMENSION: 'text-primary',
} as const;

export function DriverRankingPanel({
 graphData,
 impactEvidence,
 selectedDriverId,
 onSelectDriver,
 onHoverDriver,
}: DriverRankingPanelProps) {
 const { t } = useTranslation();
 const [search, setSearch] = useState('');

 const rankings: DriverRankItem[] = useMemo(() => {
 if (!graphData) return [];
 return deriveDriverRankings(graphData, impactEvidence);
 }, [graphData, impactEvidence]);

 const filtered = useMemo(() => {
 if (!search.trim()) return rankings;
 const q = search.toLowerCase();
 return rankings.filter((r) => r.label.toLowerCase().includes(q));
 }, [rankings, search]);

 if (!graphData) {
 return (
 <div className="text-xs text-foreground0 text-center py-4">
 {t('insight.driverRanking.noGraph')}
 </div>
 );
 }

 if (rankings.length === 0) {
 return (
 <div className="text-xs text-foreground0 text-center py-4">
 <Columns3 className="h-5 w-5 mx-auto mb-2 opacity-30" />
 {t('insight.driverRanking.noDrivers')}
 </div>
 );
 }

 return (
 <div className="space-y-2">
 <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
 <TrendingUp className="h-3 w-3" />
 {t('insight.driverRanking.title')}
 <span className="ml-auto text-muted-foreground normal-case font-normal">
 {t('insight.driverRanking.count', { count: rankings.length })}
 </span>
 </div>

 {/* Search */}
 <div className="relative">
 <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
 <input
 type="text"
 value={search}
 onChange={(e) => setSearch(e.target.value)}
 placeholder={t('insight.driverRanking.searchPlaceholder')}
 aria-label="드라이버 검색"
 className="w-full pl-6 pr-2 py-1 text-xs bg-muted/50 border border-border rounded text-foreground/80 placeholder-neutral-600 focus:outline-none focus:border-neutral-500"
 />
 </div>

 {/* List */}
 <div className="space-y-0.5 max-h-[calc(100vh-380px)] overflow-y-auto pr-1">
 {filtered.map((item, idx) => {
 const isSelected = selectedDriverId === item.node_id;
 const Icon = TYPE_ICON[item.type as keyof typeof TYPE_ICON] ?? TrendingUp;
 const typeColor = TYPE_COLOR[item.type as keyof typeof TYPE_COLOR] ?? 'text-muted-foreground';

 return (
 <button
 type="button"
 key={item.node_id}
 onClick={() => onSelectDriver(item.node_id)}
 onMouseEnter={() => onHoverDriver?.(item.node_id)}
 onMouseLeave={() => onHoverDriver?.(null)}
 className={cn(
 'w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors',
 isSelected
 ? 'bg-primary/15 border border-primary/30'
 : 'hover:bg-muted/50 border border-transparent',
 )}
 >
 {/* Rank */}
 <span className="text-[10px] font-mono text-muted-foreground w-4 text-right shrink-0">
 {idx + 1}
 </span>

 {/* Type icon */}
 <Icon className={cn('h-3 w-3 shrink-0', typeColor)} />

 {/* Label */}
 <div className="flex-1 min-w-0">
 <div className="text-xs text-foreground truncate">{item.label}</div>
 {item.evidence_count > 0 && (
 <div className="text-[10px] text-muted-foreground">
 {t('insight.driverRanking.evidenceCount', { count: item.evidence_count })}
 </div>
 )}
 </div>

 {/* Score */}
 <span
 className={cn(
 'shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
 scoreColor(item.score),
 scoreBgColor(item.score),
 )}
 >
 {formatScoreRaw(item.score)}
 </span>
 </button>
 );
 })}

 {filtered.length === 0 && (
 <div className="text-xs text-muted-foreground text-center py-2">
 {t('insight.driverRanking.noResults', { query: search })}
 </div>
 )}
 </div>
 </div>
 );
}
