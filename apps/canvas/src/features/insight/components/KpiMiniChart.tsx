// features/insight/components/KpiMiniChart.tsx
// SVG sparkline for KPI query-activity timeseries (P2-A).
// Renders a simple line chart without an external chart library.

import type { ActivityPoint } from '../api/insightApi';

interface KpiMiniChartProps {
  series: ActivityPoint[];
  width?: number;
  height?: number;
  className?: string;
}

export function KpiMiniChart({
  series,
  width = 120,
  height = 32,
  className,
}: KpiMiniChartProps) {
  if (series.length < 2) {
    return (
      <div
        style={{ width, height }}
        className={`flex items-center justify-center text-[10px] text-neutral-600 ${className ?? ''}`}
      >
        데이터 없음
      </div>
    );
  }

  const values = series.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const pad = 2;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  const toX = (i: number) => pad + (i / (series.length - 1)) * innerW;
  const toY = (v: number) => pad + innerH - ((v - min) / range) * innerH;

  const points = series.map((p, i) => `${toX(i)},${toY(p.value)}`).join(' ');
  const lastVal = values[values.length - 1];
  const prevVal = values[values.length - 2];
  const stroke = lastVal >= prevVal ? '#4ade80' : '#f87171';   // green / red

  return (
    <svg
      width={width}
      height={height}
      className={className}
      aria-label="쿼리 활동도 트렌드"
    >
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle
        cx={toX(series.length - 1)}
        cy={toY(lastVal)}
        r={2}
        fill={stroke}
      />
    </svg>
  );
}
