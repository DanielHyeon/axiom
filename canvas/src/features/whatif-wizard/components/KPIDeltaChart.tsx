/**
 * KPIDeltaChart — KPI 변화량을 보여주는 Recharts 바 차트
 *
 * 각 KPI의 베이스라인 대비 변화량(delta)을 양/음 방향으로
 * 시각화한다. 양수(개선)는 초록, 음수(악화)는 빨간색으로 표시.
 */
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart3 } from 'lucide-react';
import type { KpiDeltaSummary } from '../types/whatifWizard.types';

interface KPIDeltaChartProps {
  /** KPI 델타 데이터 */
  data: KpiDeltaSummary[];
  /** 차트 제목 */
  title?: string;
}

/** 변화율 기반 색상 결정 */
function deltaColor(pctChange: number): string {
  if (pctChange > 0) return '#10b981'; // emerald-500
  if (pctChange < 0) return '#ef4444'; // red-500
  return '#6b7280'; // gray-500
}

/** 커스텀 툴팁 */
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: KpiDeltaSummary }>;
}) {
  if (!active || !payload?.length) return null;

  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
      <p className="font-semibold mb-1">{d.name}</p>
      <div className="space-y-0.5 text-xs">
        <p>
          <span className="text-muted-foreground">베이스라인:</span>{' '}
          <span className="font-mono">{d.baseline.toFixed(2)}</span>
        </p>
        <p>
          <span className="text-muted-foreground">결과값:</span>{' '}
          <span className="font-mono">{d.result.toFixed(2)}</span>
        </p>
        <p>
          <span className="text-muted-foreground">변화량:</span>{' '}
          <span
            className="font-mono"
            style={{ color: deltaColor(d.pctChange) }}
          >
            {d.delta > 0 ? '+' : ''}
            {d.delta.toFixed(2)} ({d.pctChange > 0 ? '+' : ''}
            {d.pctChange.toFixed(1)}%)
          </span>
        </p>
      </div>
    </div>
  );
}

export function KPIDeltaChart({ data, title = 'KPI 변화량' }: KPIDeltaChartProps) {
  if (data.length === 0) return null;

  // 차트 데이터: 변화율(%) 기준으로 표시
  const chartData = data.map((d) => ({
    ...d,
    displayValue: d.pctChange,
  }));

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <BarChart3 className="w-4 h-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart
            data={chartData}
            margin={{ top: 10, right: 20, left: 10, bottom: 30 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(var(--border))"
              opacity={0.3}
            />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
              angle={-30}
              textAnchor="end"
              height={50}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
              tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v.toFixed(0)}%`}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1} />
            <Bar dataKey="displayValue" radius={[4, 4, 0, 0]} maxBarSize={48}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={deltaColor(entry.pctChange)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
