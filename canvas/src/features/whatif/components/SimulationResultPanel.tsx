/**
 * SimulationResultPanel — 시뮬레이션 결과 패널
 *
 * DAG 전파 트레이스, 타임라인, 최종 변화 요약 테이블을 표시한다.
 */
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Minus, GitBranch } from 'lucide-react';
import type { SimulationResult, SimulationTrace } from '../types/wizard';

interface SimulationResultPanelProps {
  result: SimulationResult;
}

/** 변화량에 따른 아이콘과 색상 */
function deltaConfig(delta: number) {
  if (delta > 0.01) {
    return { icon: TrendingUp, color: 'text-emerald-400', bg: 'bg-emerald-500/10' };
  }
  if (delta < -0.01) {
    return { icon: TrendingDown, color: 'text-red-400', bg: 'bg-red-500/10' };
  }
  return { icon: Minus, color: 'text-muted-foreground', bg: 'bg-muted/30' };
}

/** "nodeId::field" → 짧은 필드명 */
function shortKey(key: string): string {
  return key.split('::').pop() ?? key;
}

/** 트레이스 중복 제거 */
function dedupeTraces(traces: SimulationTrace[]): SimulationTrace[] {
  const seen = new Set<string>();
  return traces.filter((t) => {
    if (seen.has(t.modelId)) return false;
    seen.add(t.modelId);
    return true;
  });
}

export function SimulationResultPanel({ result }: SimulationResultPanelProps) {
  // 변화량 크기 순 정렬
  const sortedDeltas = Object.entries(result.deltas)
    .map(([key, delta]) => ({
      key,
      field: shortKey(key),
      baseline: result.baselineState[key] ?? 0,
      predicted: result.finalState[key] ?? 0,
      delta,
      pct: result.baselineState[key] ? (delta / result.baselineState[key]) * 100 : 0,
    }))
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  // 타임라인 일수 정렬
  const timelineDays = Object.keys(result.timeline)
    .map(Number)
    .sort((a, b) => a - b);

  const allTraces = dedupeTraces(result.traces);
  const impactTraces = allTraces.filter((t) => Math.abs(t.delta) > 1e-6);

  return (
    <div className="space-y-6">
      {/* 전파 요약 카드 */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="bg-muted/30">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold text-primary">
              {result.propagationWaves}
            </div>
            <div className="text-xs text-muted-foreground">전파 단계</div>
          </CardContent>
        </Card>
        <Card className="bg-muted/30">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold text-primary">
              {impactTraces.length}
            </div>
            <div className="text-xs text-muted-foreground">영향받은 모델</div>
          </CardContent>
        </Card>
        <Card className="bg-muted/30">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold text-primary">
              {sortedDeltas.length}
            </div>
            <div className="text-xs text-muted-foreground">변화 변수</div>
          </CardContent>
        </Card>
      </div>

      {/* 실행 로그 (타임라인) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <GitBranch className="w-4 h-4" />
            실행 로그
          </CardTitle>
        </CardHeader>
        <CardContent>
          {timelineDays.map((day) => {
            const dayTraces = dedupeTraces(result.timeline[String(day)] ?? []);
            if (dayTraces.length === 0) return null;

            return (
              <div key={day} className="mb-4 last:mb-0">
                {/* Day 헤더 */}
                <div className="text-xs font-bold bg-muted/50 rounded px-2 py-1 mb-2">
                  {day === 0 ? 'Day 0 (즉시)' : `Day +${day}`}
                </div>

                {/* 트레이스 엔트리 */}
                {dayTraces.map((trace) => {
                  const cfg = deltaConfig(trace.delta);
                  return (
                    <div
                      key={`${day}-${trace.modelId}`}
                      className="flex items-center gap-2 text-xs py-1.5 pl-4 border-l-2 border-border"
                    >
                      {/* 트리거 */}
                      <span className="text-amber-400 font-semibold max-w-[140px] truncate">
                        {trace.triggeredBy.map(shortKey).join(', ')}
                      </span>
                      <span className="text-muted-foreground">&rarr;</span>

                      {/* 모델 */}
                      <span className="text-primary font-semibold">
                        {trace.modelName}
                      </span>
                      <span className="text-muted-foreground">&rarr;</span>

                      {/* 출력 */}
                      <span className="font-semibold">
                        {shortKey(trace.outputField)}:
                      </span>
                      <span className="text-muted-foreground font-mono">
                        {trace.baselineValue.toFixed(2)} &rarr; {trace.predictedValue.toFixed(2)}
                      </span>

                      {/* 변화율 */}
                      <Badge
                        variant="outline"
                        className={cn('ml-auto text-[10px] shrink-0', cfg.color)}
                      >
                        {Math.abs(trace.delta) <= 1e-6
                          ? '0.0%'
                          : `${trace.pctChange > 0 ? '+' : ''}${trace.pctChange.toFixed(1)}%`}
                      </Badge>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* 최종 변화 요약 테이블 */}
      {sortedDeltas.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">최종 변화 요약</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50">
                    <th className="px-3 py-2 text-left font-medium">항목</th>
                    <th className="px-3 py-2 text-right font-medium">변경 전</th>
                    <th className="px-3 py-2 text-right font-medium">변경 후</th>
                    <th className="px-3 py-2 text-right font-medium">변화량</th>
                    <th className="px-3 py-2 text-right font-medium">변화율</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedDeltas.map((row) => {
                    const cfg = deltaConfig(row.delta);
                    return (
                      <tr key={row.key} className="border-t border-border">
                        <td className="px-3 py-2 font-medium">{row.field}</td>
                        <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                          {row.baseline.toFixed(2)}
                        </td>
                        <td className={cn('px-3 py-2 text-right font-mono font-semibold', cfg.color)}>
                          {row.predicted.toFixed(2)}
                        </td>
                        <td className={cn('px-3 py-2 text-right font-mono', cfg.color)}>
                          {row.delta > 0 ? '+' : ''}{row.delta.toFixed(2)}
                        </td>
                        <td className={cn('px-3 py-2 text-right font-semibold', cfg.color)}>
                          {row.pct > 0 ? '+' : ''}{row.pct.toFixed(1)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
