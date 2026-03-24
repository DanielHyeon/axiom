/**
 * 토네이도 차트 — 민감도 분석 시각화.
 * KG-7: Recharts 가로 BarChart 커스텀.
 * 각 변수의 상승/하락 영향을 양방향 막대로 표시한다.
 */

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';

interface TornadoItem {
  variable: string;
  positiveImpact: number;  // 양의 변동 영향
  negativeImpact: number;  // 음의 변동 영향
}

interface TornadoChartProps {
  data: TornadoItem[];
  title?: string;
}

export function TornadoChart({ data, title }: TornadoChartProps) {
  // 절대값 기준 정렬 (가장 영향 큰 것이 위)
  const sorted = [...data].sort(
    (a, b) => Math.abs(b.positiveImpact) + Math.abs(b.negativeImpact)
              - Math.abs(a.positiveImpact) - Math.abs(a.negativeImpact)
  );

  return (
    <div className="space-y-2">
      {title && <h3 className="text-sm font-medium">{title}</h3>}
      <ResponsiveContainer width="100%" height={Math.max(200, sorted.length * 40)}>
        <BarChart data={sorted} layout="vertical" margin={{ left: 120, right: 20, top: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} className="stroke-border" />
          <XAxis type="number" tick={{ fontSize: 11 }} className="text-muted-foreground" />
          <YAxis type="category" dataKey="variable" width={110} tick={{ fontSize: 11 }} className="text-muted-foreground" />
          <Tooltip
            formatter={(value: number) => [`${value > 0 ? '+' : ''}${value.toFixed(2)}`, '']}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid hsl(var(--border))' }}
          />
          <ReferenceLine x={0} className="stroke-border" />
          <Bar dataKey="negativeImpact" stackId="a" fill="hsl(var(--destructive))" radius={[4, 0, 0, 4]}>
            {sorted.map((_, i) => <Cell key={i} fillOpacity={0.7} />)}
          </Bar>
          <Bar dataKey="positiveImpact" stackId="a" fill="hsl(var(--success))" radius={[0, 4, 4, 0]}>
            {sorted.map((_, i) => <Cell key={i} fillOpacity={0.7} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
