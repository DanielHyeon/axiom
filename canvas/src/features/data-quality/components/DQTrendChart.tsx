/**
 * DQTrendChart — DQ 추이 차트 (Recharts)
 * 시간에 따른 DQ 점수 + 성공/실패 테스트 수 추이를 표시합니다.
 */
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useDQTrend } from '../hooks/useDQMetrics';

export function DQTrendChart() {
  const { data: trend, isLoading } = useDQTrend(14);

  if (isLoading) {
    return <div className="h-64 animate-pulse rounded-lg bg-muted" />;
  }

  if (!trend || trend.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-muted-foreground border border-border rounded-lg bg-card">
        추이 데이터가 없습니다.
      </div>
    );
  }

  // 날짜 형식: MM/DD
  const formatted = trend.map((p) => ({
    ...p,
    label: p.date.slice(5).replace('-', '/'),
  }));

  return (
    <div className="border border-border rounded-lg bg-card p-5">
      <h3 className="text-sm font-semibold text-foreground mb-4">데이터 품질 추이 (최근 14일)</h3>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={formatted} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
          />
          <YAxis
            yAxisId="left"
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
            label={{ value: '점수', angle: -90, position: 'insideLeft', style: { fontSize: 11, fill: 'var(--muted-foreground)' } }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            axisLine={{ stroke: 'var(--border)' }}
            label={{ value: '테스트 수', angle: 90, position: 'insideRight', style: { fontSize: 11, fill: 'var(--muted-foreground)' } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              fontSize: '12px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
          {/* DQ 점수 영역 */}
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="score"
            name="DQ 점수"
            stroke="#3b82f6"
            fill="#3b82f6"
            fillOpacity={0.1}
            strokeWidth={2}
          />
          {/* 성공 테스트 바 */}
          <Bar yAxisId="right" dataKey="testsPassed" name="성공" fill="#22c55e" barSize={12} radius={[2, 2, 0, 0]} />
          {/* 실패 테스트 바 */}
          <Bar yAxisId="right" dataKey="testsFailed" name="실패" fill="#ef4444" barSize={12} radius={[2, 2, 0, 0]} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
