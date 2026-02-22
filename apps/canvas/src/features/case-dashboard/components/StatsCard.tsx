
interface StatsCardProps {
  label: string;
  value: number;
  trend?: 'up' | 'down' | 'same';
  trendLabel?: string;
}

export function StatsCard({ label, value, trend, trendLabel }: StatsCardProps) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <p className="text-sm text-neutral-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
      {trend != null && trendLabel != null && (
        <p className="mt-1 text-xs text-neutral-500">
          {trend === 'up' && '▲ '}
          {trend === 'down' && '▼ '}
          {trend === 'same' && '━ '}
          {trendLabel}
        </p>
      )}
    </div>
  );
}
