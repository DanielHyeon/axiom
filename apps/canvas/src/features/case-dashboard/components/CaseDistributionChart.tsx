import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import type { Case } from '../hooks/useCases';

const COLORS = ['#3b82f6', '#eab308', '#22c55e', '#ef4444'];

export function CaseDistributionChart({ cases }: { cases: Case[] }) {
  const byStatus = React.useMemo(() => {
    const map: Record<string, number> = {};
    for (const c of cases) {
      map[c.status] = (map[c.status] ?? 0) + 1;
    }
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [cases]);

  if (byStatus.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
        <h3 className="text-sm font-semibold text-white">유형별 분포</h3>
        <p className="mt-2 text-sm text-neutral-500">데이터 없음</p>
      </div>
    );
  }

  const statusLabel: Record<string, string> = {
    PENDING: '대기',
    IN_PROGRESS: '진행 중',
    COMPLETED: '완료',
    REJECTED: '반려',
  };

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-white">상태별 분포</h3>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={byStatus.map((d) => ({ ...d, name: statusLabel[d.name] ?? d.name }))}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            paddingAngle={2}
            dataKey="value"
          >
            {byStatus.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
