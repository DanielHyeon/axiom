// pages/insight/components/InsightHeader.tsx
// Insight page header with title and time range selector

import { Lightbulb } from 'lucide-react';
import { TimeRangeSelector } from '@/features/insight/components/TimeRangeSelector';
import type { TimeRange } from '@/features/insight/types/insight';

interface InsightHeaderProps {
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
}

export function InsightHeader({
  timeRange,
  onTimeRangeChange,
}: InsightHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-neutral-800 bg-neutral-900/50 px-5 py-3">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10">
          <Lightbulb className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-neutral-100">Insight</h1>
          <p className="text-xs text-neutral-500">KPI Impact 분석</p>
        </div>
      </div>

      <TimeRangeSelector value={timeRange} onChange={onTimeRangeChange} />
    </div>
  );
}
