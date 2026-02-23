
interface StatsCardProps {
  label: string;
  value: number;
  trend?: 'up' | 'down' | 'same';
  trendLabel?: string;
}

export function StatsCard({ label, value, trend, trendLabel }: StatsCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-sm text-secondary-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
      {trend != null && trendLabel != null && (
        <p className="mt-1 text-xs text-secondary-foreground">
          {trend === 'up' && '▲ '}
          {trend === 'down' && '▼ '}
          {trend === 'same' && '━ '}
          {trendLabel}
        </p>
      )}
    </div>
  );
}
