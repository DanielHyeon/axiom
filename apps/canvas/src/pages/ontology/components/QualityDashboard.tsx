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
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between h-[52px] px-6 border-b border-[#E5E5E5] shrink-0">
        <span className="text-[13px] font-semibold text-black font-[Sora]">데이터 품질</span>
        <button type="button" onClick={onClose} className="text-[#999] hover:text-black text-lg transition-colors">
          ×
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-[#999]" />
          </div>
        )}

        {error && (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-600">
            {error}
          </div>
        )}

        {report && (
          <>
            {/* Summary stats */}
            <div className="text-[11px] text-[#999] font-[IBM_Plex_Mono] mb-1">
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
              <div className="text-[11px] font-semibold text-[#999] font-[IBM_Plex_Mono] uppercase tracking-wider">계층별 커버리지</div>
              {Object.entries(report.coverage_by_layer).map(([layer, data]) => {
                const pct = data.total > 0 ? Math.round((data.verified / data.total) * 100) : 0;
                return (
                  <div key={layer} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px] capitalize border-[#E5E5E5] font-[IBM_Plex_Mono]">
                          {layer}
                        </Badge>
                        <span className="text-[#999] font-[IBM_Plex_Mono]">
                          {data.verified}/{data.total}
                        </span>
                      </div>
                      <span
                        className={cn(
                          'font-[IBM_Plex_Mono] text-[11px]',
                          pct >= 80 ? 'text-green-500' : pct >= 50 ? 'text-amber-500' : 'text-red-500',
                        )}
                      >
                        {pct}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-[#E5E5E5] overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all', LAYER_COLORS[layer] ?? 'bg-[#999]')}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    {data.orphan > 0 && (
                      <div className="text-[10px] text-amber-500 pl-1 font-[IBM_Plex_Mono]">
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
                <div className="text-[11px] font-semibold text-[#999] font-[IBM_Plex_Mono] uppercase tracking-wider">중복 이름 상세</div>
                {Object.entries(report.duplicate_details).map(([name, count]) => (
                  <div key={name} className="flex items-center justify-between text-xs text-[#5E5E5E]">
                    <span className="truncate max-w-[180px] font-[IBM_Plex_Mono]">{name}</span>
                    <Badge variant="outline" className="text-[10px] border-[#E5E5E5] font-[IBM_Plex_Mono]">
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
    <div className="rounded border border-[#E5E5E5] bg-white p-2.5 space-y-1">
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="text-[11px] text-[#999] font-[IBM_Plex_Mono]">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={cn('text-lg font-semibold tabular-nums font-[Sora]', `text-${color}-500`)}>
          {value}
        </span>
        <span className="text-[10px] text-[#999] font-[IBM_Plex_Mono]">/ {total} ({pct}%)</span>
      </div>
    </div>
  );
}
