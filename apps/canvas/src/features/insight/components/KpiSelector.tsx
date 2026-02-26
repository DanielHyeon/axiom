// features/insight/components/KpiSelector.tsx
// Manual KPI fingerprint input with sample KPI quick buttons

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Zap } from 'lucide-react';

interface KpiSelectorProps {
  onSelect: (kpiId: string, fingerprint: string) => void;
  loading?: boolean;
}

const SAMPLE_KPIS = [
  { id: 'orders_pending_count', label: 'Orders Pending' },
  { id: 'revenue_total', label: 'Revenue Total' },
  { id: 'invoice_count', label: 'Invoice Count' },
  { id: 'ar_balance', label: 'AR Balance' },
  { id: 'customer_churn_rate', label: 'Churn Rate' },
];

export function KpiSelector({ onSelect, loading }: KpiSelectorProps) {
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = inputValue.trim();
      if (trimmed) {
        onSelect(trimmed, trimmed);
      }
    },
    [inputValue, onSelect],
  );

  const handleQuickSelect = useCallback(
    (kpi: { id: string; label: string }) => {
      setInputValue(kpi.id);
      onSelect(kpi.id, kpi.id);
    },
    [onSelect],
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs font-medium text-neutral-400 uppercase tracking-wider">
        <Search className="h-3 w-3" />
        KPI 선택
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="KPI fingerprint 입력..."
          className="h-8 text-xs bg-neutral-800/50 border-neutral-700"
          disabled={loading}
        />
        <Button
          type="submit"
          size="sm"
          className="h-8 px-3 text-xs shrink-0"
          disabled={!inputValue.trim() || loading}
        >
          <Zap className="h-3 w-3 mr-1" />
          분석
        </Button>
      </form>

      <div className="space-y-1">
        <div className="text-[10px] font-medium text-neutral-500 uppercase tracking-wider">
          샘플 KPI
        </div>
        <div className="flex flex-wrap gap-1">
          {SAMPLE_KPIS.map((kpi) => (
            <button
              key={kpi.id}
              onClick={() => handleQuickSelect(kpi)}
              disabled={loading}
              className="rounded-full border border-neutral-700 bg-neutral-800/30 px-2.5 py-0.5 text-[10px] text-neutral-400 transition-colors hover:border-primary/50 hover:text-primary hover:bg-primary/10 disabled:opacity-50"
            >
              {kpi.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
