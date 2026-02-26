// features/insight/components/NodeDetailPanel.tsx
// Side panel for driver/node detail — uses graph node data + compact evidence

import { X, BarChart3, FileSearch, Loader2, TrendingUp, Layers, Target, GitMerge } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { GraphNode, CompactEvidence } from '../types/insight';
import { formatScore, scoreColor, formatBreakdownValue } from '../utils/scoreCalculator';

interface NodeDetailPanelProps {
  nodeId: string | null;
  graphNode: GraphNode | null;
  evidence: CompactEvidence[] | null;
  loading: boolean;
  onClose: () => void;
}

const BREAKDOWN_LABELS: Record<string, string> = {
  usage:              '사용 빈도',
  kpi_connection:     'KPI 연결성',
  centrality:         '중심성',
  discriminative:     '판별력',
  volatility:         '변동성',
  cardinality_adjust: '카디널리티 보정',
  sample_size_guard:  '표본수 보정',
  cooccur_with_kpi:   'KPI 동시출현',
};

const NODE_TYPE_LABEL: Record<string, string> = {
  KPI:       'KPI',
  DRIVER:    'Driver',
  DIMENSION: 'Dimension',
  TRANSFORM: 'Transform',
};

const NODE_TYPE_COLOR: Record<string, string> = {
  KPI:       'text-blue-400',
  DRIVER:    'text-orange-400',
  DIMENSION: 'text-purple-400',
  TRANSFORM: 'text-neutral-400',
};

function NodeTypeIcon({ type }: { type: string }) {
  const cls = 'h-4 w-4';
  switch (type) {
    case 'KPI':       return <Target className={cls} />;
    case 'DRIVER':    return <TrendingUp className={cls} />;
    case 'DIMENSION': return <Layers className={cls} />;
    default:          return <GitMerge className={cls} />;
  }
}

export function NodeDetailPanel({
  nodeId,
  graphNode,
  evidence,
  loading,
  onClose,
}: NodeDetailPanelProps) {
  if (!nodeId) return null;

  const breakdown = graphNode?.meta as Record<string, number> | undefined;
  const hasBreakdown = breakdown && Object.keys(breakdown).length > 0;

  return (
    <div className="flex flex-col h-full border-l border-neutral-800 bg-neutral-900/95">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-neutral-200">노드 상세</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-neutral-500 hover:text-neutral-200"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-neutral-500" />
          </div>
        )}

        {!loading && graphNode && (
          <>
            {/* Node identity */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className={NODE_TYPE_COLOR[graphNode.type] ?? 'text-neutral-400'}>
                  <NodeTypeIcon type={graphNode.type} />
                </span>
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded bg-neutral-800 ${NODE_TYPE_COLOR[graphNode.type] ?? 'text-neutral-400'}`}
                >
                  {NODE_TYPE_LABEL[graphNode.type] ?? graphNode.type}
                </span>
              </div>
              <div className="text-sm font-medium text-neutral-100 break-all">
                {graphNode.label}
              </div>
              <div className="text-[10px] text-neutral-600 font-mono break-all">
                {graphNode.id}
              </div>
            </div>

            {/* Score */}
            {graphNode.score != null && (
              <div className="rounded-lg border border-neutral-800 bg-neutral-800/30 p-3">
                <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
                  영향 점수
                </div>
                <div className={`text-2xl font-bold ${scoreColor(graphNode.score)}`}>
                  {formatScore(graphNode.score)}
                </div>
              </div>
            )}

            {/* Score breakdown (from node.meta) */}
            {hasBreakdown && (
              <div>
                <div className="text-xs font-medium text-neutral-300 mb-2">점수 분해</div>
                <div className="space-y-1.5">
                  {Object.entries(breakdown!).map(([key, value]) => {
                    if (typeof value !== 'number') return null;
                    const label = BREAKDOWN_LABELS[key] ?? key;
                    const isNegative = value < 0;
                    const barWidth = Math.min(Math.abs(value) * 100 * 3, 100);

                    return (
                      <div key={key} className="flex items-center gap-2">
                        <div className="w-24 text-[10px] text-neutral-400 truncate" title={label}>
                          {label}
                        </div>
                        <div className="flex-1 h-2 bg-neutral-800 rounded-full overflow-hidden">
                          <div
                            style={{ '--bar-w': `${barWidth}%` } as React.CSSProperties}
                            className={`h-full rounded-full transition-all [width:var(--bar-w)] ${
                              isNegative ? 'bg-red-500/60' : 'bg-emerald-500/60'
                            }`}
                          />
                        </div>
                        <div
                          className={`w-12 text-right text-[10px] font-mono ${
                            isNegative ? 'text-red-400' : 'text-emerald-400'
                          }`}
                        >
                          {formatBreakdownValue(value)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Evidence */}
            <div>
              <div className="flex items-center gap-2 text-xs font-medium text-neutral-300 mb-2">
                <FileSearch className="h-3 w-3" />
                관련 쿼리
                {evidence && evidence.length > 0 && (
                  <span className="text-neutral-600">({evidence.length}건)</span>
                )}
              </div>

              {evidence && evidence.length > 0 ? (
                <div className="space-y-2">
                  {evidence.map((ev, idx) => (
                    <div
                      key={idx}
                      className="rounded border border-neutral-800 bg-neutral-800/20 p-2 space-y-1"
                    >
                      <div className="flex justify-between text-[10px] text-neutral-600">
                        <span className="font-mono">{ev.query_id.slice(0, 16)}…</span>
                        <span>
                          {ev.executed_at
                            ? new Date(ev.executed_at).toLocaleDateString('ko-KR')
                            : ''}
                        </span>
                      </div>
                      {Array.isArray(ev.tables) && ev.tables.length > 0 && (
                        <div className="text-[10px] text-neutral-400">
                          테이블:{' '}
                          {(ev.tables as Array<{ name?: string } | string>)
                            .map((t) => (typeof t === 'string' ? t : t.name ?? ''))
                            .filter(Boolean)
                            .join(', ')}
                        </div>
                      )}
                      {Array.isArray(ev.select) && ev.select.length > 0 && (
                        <div className="text-[10px] text-neutral-500 truncate">
                          SELECT:{' '}
                          {(ev.select as Array<{ expr?: string } | string>)
                            .map((s) => (typeof s === 'string' ? s : s.expr ?? ''))
                            .filter(Boolean)
                            .slice(0, 4)
                            .join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-[10px] text-neutral-600 italic py-2">
                  이 노드에 대한 근거 쿼리가 없습니다
                </div>
              )}
            </div>
          </>
        )}

        {!loading && !graphNode && (
          <div className="text-xs text-neutral-500 text-center py-8">
            노드 데이터를 불러올 수 없습니다
          </div>
        )}
      </div>
    </div>
  );
}
