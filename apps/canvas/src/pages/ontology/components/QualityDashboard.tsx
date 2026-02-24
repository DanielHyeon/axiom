import { useState, useEffect } from 'react';
import { getQualityReport } from '@/features/ontology/api/ontologyApi';
import type { QualityReport } from '@/features/ontology/types/ontology';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  AlertTriangle,
  CheckCircle,
  FileQuestion,
  Copy,
  X,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface QualityDashboardProps {
  caseId: string;
  onClose: () => void;
}

const LAYER_COLORS: Record<string, string> = {
  kpi: 'bg-violet-500',
  measure: 'bg-blue-500',
  process: 'bg-emerald-500',
  resource: 'bg-amber-500',
};

export function QualityDashboard({ caseId, onClose }: QualityDashboardProps) {
  const [report, setReport] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getQualityReport(caseId)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message || 'Failed to load quality report');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [caseId]);

  return (
    <div className="w-80 border-l border-neutral-800 bg-[#161616] flex flex-col shrink-0 overflow-hidden">
      {/* Header */}
      <div className="h-12 border-b border-neutral-800 flex items-center justify-between px-3 shrink-0">
        <span className="text-sm font-medium text-neutral-200">데이터 품질</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
          <X className="h-4 w-4 text-neutral-400" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-neutral-500" />
          </div>
        )}

        {error && (
          <div className="rounded border border-red-900/50 bg-red-900/20 p-3 text-sm text-red-200">
            {error}
          </div>
        )}

        {report && (
          <>
            {/* Summary stats */}
            <div className="text-xs text-neutral-500 mb-1">
              전체: {report.total_nodes} nodes, {report.total_relations} relations
            </div>

            {/* Stat cards */}
            <div className="grid grid-cols-2 gap-2">
              <StatCard
                icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
                label="고립 노드"
                value={report.orphan_count}
                total={report.total_nodes}
                color="amber"
              />
              <StatCard
                icon={<CheckCircle className="h-4 w-4 text-red-500" />}
                label="미검증"
                value={report.low_confidence_count}
                total={report.total_nodes}
                color="red"
              />
              <StatCard
                icon={<FileQuestion className="h-4 w-4 text-blue-500" />}
                label="설명 없음"
                value={report.missing_description}
                total={report.total_nodes}
                color="blue"
              />
              <StatCard
                icon={<Copy className="h-4 w-4 text-purple-500" />}
                label="중복 이름"
                value={report.duplicate_names}
                total={report.total_nodes}
                color="purple"
              />
            </div>

            {/* Coverage by layer */}
            <div className="space-y-2">
              <div className="text-xs font-medium text-neutral-400">계층별 커버리지</div>
              {Object.entries(report.coverage_by_layer).map(([layer, data]) => {
                const pct = data.total > 0 ? Math.round((data.verified / data.total) * 100) : 0;
                return (
                  <div key={layer} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px] capitalize border-neutral-700">
                          {layer}
                        </Badge>
                        <span className="text-neutral-500">
                          {data.verified}/{data.total}
                        </span>
                      </div>
                      <span
                        className={cn(
                          'font-mono text-[11px]',
                          pct >= 80 ? 'text-green-400' : pct >= 50 ? 'text-amber-400' : 'text-red-400',
                        )}
                      >
                        {pct}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-neutral-800 overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all', LAYER_COLORS[layer] ?? 'bg-neutral-500')}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    {data.orphan > 0 && (
                      <div className="text-[10px] text-amber-500/70 pl-1">
                        고립: {data.orphan}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Duplicate details */}
            {report.duplicate_names > 0 && (
              <div className="space-y-1">
                <div className="text-xs font-medium text-neutral-400">중복 이름 상세</div>
                {Object.entries(report.duplicate_details).map(([name, count]) => (
                  <div key={name} className="flex items-center justify-between text-xs text-neutral-400">
                    <span className="truncate max-w-[180px]">{name}</span>
                    <Badge variant="outline" className="text-[10px] border-neutral-700">
                      x{count}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  total,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-2.5 space-y-1">
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="text-[11px] text-neutral-500">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={cn('text-lg font-bold tabular-nums', `text-${color}-400`)}>
          {value}
        </span>
        <span className="text-[10px] text-neutral-600">/ {total} ({pct}%)</span>
      </div>
    </div>
  );
}
