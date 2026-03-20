// pages/insight/components/InsightHeader.tsx
// Insight page header with title, KPI search, and time range selector

import { useTranslation } from 'react-i18next';
import { Search, Zap } from 'lucide-react';
import { TimeRangeSelector } from '@/features/insight/components/TimeRangeSelector';
import type { TimeRange } from '@/features/insight/types/insight';

interface InsightHeaderProps {
 timeRange: TimeRange;
 onTimeRangeChange: (range: TimeRange) => void;
 kpiFingerprint?: string | null;
 onSearchSubmit?: () => void;
}

export function InsightHeader({
 timeRange,
 onTimeRangeChange,
}: InsightHeaderProps) {
 const { t } = useTranslation();
 return (
 <div className="flex items-center justify-between">
 <div className="space-y-1.5">
 <h1 className="text-[48px] font-semibold tracking-[-2px] text-black font-[Sora]">{t('insight.title')}</h1>
 <p className="text-[13px] text-[#5E5E5E] font-[IBM_Plex_Mono]">
 {t('insight.subtitle')}
 </p>
 </div>
 <div className="flex items-center gap-3">
 <div className="flex items-center gap-2 w-[220px] px-4 py-2.5 border border-[#E5E5E5] rounded">
 <Search className="h-3.5 w-3.5 text-foreground/60" />
 <span className="text-[13px] text-foreground/60 font-[IBM_Plex_Mono]">{t('insight.searchKpi')}</span>
 </div>
 <button
 type="button"
 className="flex items-center gap-2 px-4 py-2.5 bg-destructive text-white text-[12px] font-medium font-[Sora] rounded hover:bg-red-700 transition-colors"
 >
 <Zap className="h-3.5 w-3.5" />
 {t('common.analyze')}
 </button>
 <TimeRangeSelector value={timeRange} onChange={onTimeRangeChange} />
 </div>
 </div>
 );
}
