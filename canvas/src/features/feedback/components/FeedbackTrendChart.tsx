/**
 * FeedbackTrendChart — 일별/주별 피드백 추이 차트.
 *
 * Recharts AreaChart를 사용하여 positive/negative/partial 피드백을
 * 시계열로 시각화한다.
 */
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { FeedbackTrendPoint } from '../types/feedback';

interface FeedbackTrendChartProps {
  data: FeedbackTrendPoint[] | undefined;
  isLoading: boolean;
}

export function FeedbackTrendChart({ data, isLoading }: FeedbackTrendChartProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold font-[Sora]">피드백 추이</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-64 flex items-center justify-center">
            <div className="animate-pulse text-xs text-muted-foreground">로딩 중...</div>
          </div>
        ) : !data || data.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
            데이터가 없습니다
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E5E5" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }}
                tickFormatter={(v: string) => {
                  // YYYY-MM-DD -> MM/DD
                  const parts = v.split('-');
                  return `${parts[1]}/${parts[2]}`;
                }}
              />
              <YAxis tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} />
              <Tooltip
                contentStyle={{
                  fontSize: 12,
                  fontFamily: 'IBM Plex Mono',
                  borderRadius: 8,
                  border: '1px solid #E5E5E5',
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }}
              />
              <Area
                type="monotone"
                dataKey="positive"
                name="긍정"
                stackId="1"
                stroke="#22c55e"
                fill="#22c55e"
                fillOpacity={0.3}
              />
              <Area
                type="monotone"
                dataKey="negative"
                name="부정"
                stackId="1"
                stroke="#ef4444"
                fill="#ef4444"
                fillOpacity={0.3}
              />
              <Area
                type="monotone"
                dataKey="partial"
                name="수정"
                stackId="1"
                stroke="#f59e0b"
                fill="#f59e0b"
                fillOpacity={0.3}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
