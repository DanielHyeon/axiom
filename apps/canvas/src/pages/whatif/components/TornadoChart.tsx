// src/pages/whatif/components/TornadoChart.tsx

import type { SensitivityData } from '@/features/whatif/types/whatif';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';

interface TornadoChartProps {
    data: SensitivityData[];
    baseValue: number;
}

export function TornadoChart({ data, baseValue }: TornadoChartProps) {
    // To draw a tornado chart with Recharts, we plot the deviations from the base.
    // We need two bars for each parameter: one for decrease impact, one for increase impact.
    // Recharts stacked bars can work if we separate negative and positive values relative to 0.

    const chartData = data.map(d => {
        // Determine which direction is Negative or Positive relative to the overall metric
        // Here we assume high_value > base_value means positive impact on chart (to the right)
        const lowDiff = d.low_value - baseValue;
        const highDiff = d.high_value - baseValue;

        return {
            name: d.parameter_label,
            // We map these so that Negative values go left, Positive go right
            decreaseImpact: lowDiff,
            increaseImpact: highDiff,
        };
    });

    return (
        <div className="w-full h-80">
            <h3 className="text-sm font-medium text-neutral-300 mb-4 text-center">민감도 분석 (Tornado Chart)</h3>
            <div className="w-full text-xs text-neutral-500 flex justify-between px-12 mb-2">
                <span>◄ 감소 영향</span>
                <span>증가 영향 ►</span>
            </div>
            <ResponsiveContainer width="100%" height="80%">
                <BarChart
                    layout="vertical"
                    data={chartData}
                    margin={{ top: 0, right: 30, left: 20, bottom: 5 }}
                    stackOffset="sign"
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={false} />
                    <XAxis type="number" stroke="#666" fontSize={12} tickFormatter={(v) => v > 0 ? `+${v}` : v} />
                    <YAxis dataKey="name" type="category" width={100} stroke="#888" fontSize={12} />
                    <Tooltip
                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                        contentStyle={{ backgroundColor: '#1a1a1a', borderColor: '#333' }}
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        formatter={(val: any) => [val > 0 ? `+${Number(val).toFixed(1)}` : Number(val).toFixed(1), 'Impact']}
                    />
                    <ReferenceLine x={0} stroke="#888" />
                    <Bar dataKey="decreaseImpact" stackId="a" fill="#ef4444" radius={[4, 0, 0, 4]} barSize={20} />
                    <Bar dataKey="increaseImpact" stackId="a" fill="#10b981" radius={[0, 4, 4, 0]} barSize={20} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
