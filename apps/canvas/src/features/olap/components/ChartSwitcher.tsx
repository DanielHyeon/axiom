import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

export type ChartViewType = 'table' | 'bar' | 'line' | 'pie';

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b'];

interface ChartSwitcherProps {
  viewType: ChartViewType;
  onViewChange: (view: ChartViewType) => void;
  headers: string[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[][];
  tableComponent: React.ReactNode;
}

/** Table/Bar/Line/Pie 전환, 데이터 유지 */
export function ChartSwitcher({ viewType, onViewChange, headers, data, tableComponent }: ChartSwitcherProps) {
  const chartData = data.map((row) => {
    const obj: Record<string, unknown> = {};
    headers.forEach((h, i) => {
      obj[h] = row[i];
    });
    return obj;
  });

  const firstDim = headers[0];
  const firstMeasure = headers.length > 1 ? headers[headers.length - 1] : headers[0];

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {(['table', 'bar', 'line', 'pie'] as const).map((view) => (
          <button
            key={view}
            type="button"
            onClick={() => onViewChange(view)}
            className={`rounded px-2 py-1 text-sm ${
              viewType === view ? 'bg-blue-600 text-white' : 'bg-neutral-800 text-neutral-400 hover:text-white'
            }`}
          >
            {view === 'table' ? '테이블' : view === 'bar' ? '막대' : view === 'line' ? '선' : '파이'}
          </button>
        ))}
      </div>

      {viewType === 'table' && tableComponent}

      {viewType === 'bar' && chartData.length > 0 && (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey={firstDim} stroke="#888" fontSize={12} />
              <YAxis stroke="#888" fontSize={12} />
              <Tooltip contentStyle={{ backgroundColor: '#1e1e1e', borderColor: '#333' }} />
              <Bar dataKey={firstMeasure} fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {viewType === 'line' && chartData.length > 0 && (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey={firstDim} stroke="#888" fontSize={12} />
              <YAxis stroke="#888" fontSize={12} />
              <Tooltip contentStyle={{ backgroundColor: '#1e1e1e', borderColor: '#333' }} />
              <Line type="monotone" dataKey={firstMeasure} stroke="#8b5cf6" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {viewType === 'pie' && chartData.length > 0 && (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={80}
                paddingAngle={2}
                dataKey={firstMeasure}
                nameKey={firstDim}
              >
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: '#1e1e1e', borderColor: '#333' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
