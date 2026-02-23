import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface StatsCardProps {
  label: string;
  value: number;
  trend?: 'up' | 'down' | 'same';
  trendLabel?: string;
}

export function StatsCard({ label, value, trend, trendLabel }: StatsCardProps) {
  return (
    <div className="glass-card group rounded-xl p-5 transition-all duration-300 hover:shadow-lg hover:shadow-primary/5">
      <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums text-foreground">{value}</p>
      {trend != null && trendLabel != null && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          {trend === 'up' && <TrendingUp className="h-3.5 w-3.5 text-success" />}
          {trend === 'down' && <TrendingDown className="h-3.5 w-3.5 text-destructive" />}
          {trend === 'same' && <Minus className="h-3.5 w-3.5" />}
          <span>{trendLabel}</span>
        </div>
      )}
    </div>
  );
}
