// features/insight/components/TimeRangeSelector.tsx
// Pill-style toggle buttons for time range selection

import { cn } from '@/lib/utils';
import type { TimeRange } from '../types/insight';

interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
}

const OPTIONS: { value: TimeRange; label: string }[] = [
  { value: '7d', label: '7일' },
  { value: '30d', label: '30일' },
  { value: '90d', label: '90일' },
];

export function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  return (
    <div className="inline-flex rounded-lg border border-neutral-700 bg-neutral-800/50 p-0.5">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-md px-3 py-1 text-xs font-medium transition-all duration-150',
            value === opt.value
              ? 'bg-primary text-white shadow-sm'
              : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-700/50',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
