/**
 * ParameterSweepChart — 파라미터 스윕 차트
 *
 * 시뮬레이션 결과의 변화량을 바 차트로 시각화한다.
 * Recharts BarChart를 사용하여 각 변수의 변화율을 비교한다.
 */
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SimulationResult } from '../types/wizard';

interface ParameterSweepChartProps {
  result: SimulationResult;
}

/** "nodeId::field" → 짧은 필드명 */
function shortKey(key: string): string {
  return key.split('::').pop() ?? key;
}

export function ParameterSweepChart({ result }: ParameterSweepChartProps) {
  // 변화율 데이터 준비
  const chartData = Object.entries(result.deltas)
    .map(([key, delta]) => {
      const baseline = result.baselineState[key] ?? 0;
      const pct = baseline !== 0 ? (delta / baseline) * 100 : 0;
      return {
        name: shortKey(key),
        fullKey: key,
        delta,
        pct: Math.round(pct * 10) / 10,
        baseline,
        predicted: result.finalState[key] ?? 0,
      };
    })
    .filter((d) => Math.abs(d.delta) > 1e-6)
    .sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct));

  if (chartData.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          시뮬레이션에서 변화가 감지되지 않았습니다.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">변화율 비교 차트</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                horizontal={false}
              />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={{ stroke: 'hsl(var(--border))' }}
                tickFormatter={(v: number) => `${v}%`}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tick={{ fontSize: 11, fill: 'hsl(var(--foreground))' }}
                axisLine={{ stroke: 'hsl(var(--border))' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                labelStyle={{ fontWeight: 600 }}
                formatter={(value: number, _name: string, entry: { payload: { baseline: number; predicted: number } }) => [
                  `${value > 0 ? '+' : ''}${value}% (${entry.payload.baseline.toFixed(2)} -> ${entry.payload.predicted.toFixed(2)})`,
                  '변화율',
                ]}
              />
              <ReferenceLine x={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
              <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, idx) => (
                  <Cell
                    key={idx}
                    fill={entry.pct >= 0 ? 'hsl(142, 71%, 45%)' : 'hsl(0, 84%, 60%)'}
                    fillOpacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
