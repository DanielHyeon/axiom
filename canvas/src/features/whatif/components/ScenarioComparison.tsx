/**
 * 시나리오 비교 테이블 — 복수 시나리오 결과 열 비교.
 * KG-7: 기준 시나리오 대비 각 시나리오의 차이를 표로 표시한다.
 */

import { Badge } from '@/components/ui/badge';

interface ScenarioResult {
  id: string;
  name: string;
  values: Record<string, number>; // variableName → value
}

interface ScenarioComparisonProps {
  baseline: ScenarioResult;
  scenarios: ScenarioResult[];
  variables: string[];
}

function formatDiff(baseline: number, value: number): { text: string; className: string } {
  const diff = value - baseline;
  const pct = baseline !== 0 ? (diff / baseline) * 100 : 0;
  if (Math.abs(diff) < 0.001) return { text: '-', className: 'text-muted-foreground' };
  return {
    text: `${diff > 0 ? '+' : ''}${pct.toFixed(1)}%`,
    className: diff > 0 ? 'text-success' : 'text-destructive',
  };
}

export function ScenarioComparison({ baseline, scenarios, variables }: ScenarioComparisonProps) {
  return (
    <div className="border border-border rounded-lg overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted border-b border-border">
            <th className="px-3 py-2 text-left font-medium">변수</th>
            <th className="px-3 py-2 text-right font-medium">
              <div className="flex items-center justify-end gap-1">
                {baseline.name}
                <Badge variant="outline" className="text-[10px]">기준</Badge>
              </div>
            </th>
            {scenarios.map((s) => (
              <th key={s.id} className="px-3 py-2 text-right font-medium">{s.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {variables.map((v) => (
            <tr key={v} className="border-b border-border hover:bg-muted/30">
              <td className="px-3 py-2 text-muted-foreground">{v}</td>
              <td className="px-3 py-2 text-right font-mono">{baseline.values[v]?.toFixed(2) ?? '-'}</td>
              {scenarios.map((s) => {
                const baseVal = baseline.values[v] ?? 0;
                const val = s.values[v] ?? 0;
                const { text, className } = formatDiff(baseVal, val);
                return (
                  <td key={s.id} className="px-3 py-2 text-right">
                    <span className="font-mono">{val.toFixed(2)}</span>
                    <span className={`ml-2 text-xs ${className}`}>{text}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
