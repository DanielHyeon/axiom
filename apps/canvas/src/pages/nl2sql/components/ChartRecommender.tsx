import { useMemo } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    LineChart, Line, PieChart, Pie, Cell,
    ScatterChart, Scatter
} from 'recharts';
import type { ChartConfig } from '@/features/nl2sql/types/nl2sql';

interface ChartRecommenderProps {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    data: any[];
    config: ChartConfig;
}

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b'];

export function ChartRecommender({ data, config }: ChartRecommenderProps) {
    const chartData = useMemo(() => {
        // Convert 'row' array structure from useNl2sqlMock into array of objects for Recharts
        // If the data is already array of objects, this just passes it through
        return data;
    }, [data]);

    const { chart_type, config: innerConfig } = config;

    if (!data || data.length === 0) return null;

    // KPI Card: large centered number display
    if (chart_type === 'kpi_card') {
        const valueColumn = innerConfig.value_column || Object.keys(data[0] || {})[0];
        const rawValue = data[0]?.[valueColumn];
        const label = innerConfig.label || valueColumn;
        const formattedValue =
            typeof rawValue === 'number'
                ? rawValue.toLocaleString(undefined, { maximumFractionDigits: 2 })
                : String(rawValue ?? '--');

        return (
            <div className="w-full border border-[#E5E5E5] rounded-md bg-white p-6 mt-2 mb-4 flex flex-col items-center justify-center min-h-[180px]">
                <div className="text-xs font-medium text-[#999] uppercase tracking-wider mb-2 font-[IBM_Plex_Mono]">KPI</div>
                <div className="text-5xl font-bold text-black tabular-nums tracking-tight font-[Sora]">
                    {formattedValue}
                </div>
                <div className="text-sm text-[#999] mt-3 font-[IBM_Plex_Mono]">{label}</div>
            </div>
        );
    }

    return (
        <div className="w-full h-72 border border-[#E5E5E5] rounded-md bg-white p-4 mt-2 mb-4">
            <div className="text-sm font-medium text-[#5E5E5E] mb-4 flex justify-between items-center font-[Sora]">
                <span>AI 추천 차트: {chart_type === 'bar' ? '막대 차트' : chart_type === 'line' ? '선 차트' : chart_type === 'pie' ? '파이 차트' : chart_type === 'scatter' ? '산점도' : '차트'}</span>
            </div>
            <ResponsiveContainer width="100%" height="85%">
                {chart_type === 'bar' ? (
                    <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E5E5E5" />
                        <XAxis dataKey={innerConfig.x_column} stroke="#999" fontSize={12} />
                        <YAxis stroke="#999" fontSize={12} />
                        <Tooltip contentStyle={{ backgroundColor: '#fff', borderColor: '#E5E5E5' }} />
                        <Bar dataKey={innerConfig.y_column} fill="#DC2626" radius={[4, 4, 0, 0]} />
                    </BarChart>
                ) : chart_type === 'line' ? (
                    <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E5E5E5" />
                        <XAxis dataKey={innerConfig.x_column} stroke="#999" fontSize={12} />
                        <YAxis stroke="#999" fontSize={12} />
                        <Tooltip contentStyle={{ backgroundColor: '#fff', borderColor: '#E5E5E5' }} />
                        <Line type="monotone" dataKey={innerConfig.y_column} stroke="#DC2626" strokeWidth={2} />
                    </LineChart>
                ) : chart_type === 'pie' ? (
                    <PieChart>
                        <Pie
                            data={chartData}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={80}
                            paddingAngle={5}
                            dataKey={innerConfig.value_column || innerConfig.y_column}
                            nameKey={innerConfig.label_column || innerConfig.x_column}
                        >
                            {chartData.map((_entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                        </Pie>
                        <Tooltip contentStyle={{ backgroundColor: '#fff', borderColor: '#E5E5E5' }} />
                    </PieChart>
                ) : chart_type === 'scatter' ? (
                    <ScatterChart margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E5E5E5" />
                        <XAxis dataKey={innerConfig.x_column} stroke="#999" fontSize={12} name={innerConfig.x_label || innerConfig.x_column} />
                        <YAxis dataKey={innerConfig.y_column} stroke="#999" fontSize={12} name={innerConfig.y_label || innerConfig.y_column} />
                        <Tooltip contentStyle={{ backgroundColor: '#fff', borderColor: '#E5E5E5' }} cursor={{ strokeDasharray: '3 3' }} />
                        <Scatter data={chartData} fill="#DC2626" />
                    </ScatterChart>
                ) : (
                    <div className="flex items-center justify-center h-full text-[#999] text-sm font-[IBM_Plex_Mono]">
                        차트 렌더링을 지원하지 않는 형식입니다.
                    </div>
                )}
            </ResponsiveContainer>
        </div>
    );
}
