import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { PieChart as PieChartIcon } from 'lucide-react';
import type { Case } from '../hooks/useCases';
import { useTranslation } from 'react-i18next';

const COLORS = ['#3b82f6', '#eab308', '#22c55e', '#ef4444'];

export function CaseDistributionChart({
  cases }: { cases: Case[] }) {
 const byStatus = useMemo(() => {
 const map: Record<string, number> = {};
 for (const c of cases) {
 map[c.status] = (map[c.status] ?? 0) + 1;
 }
 return Object.entries(map).map(([name, value]) => ({ name, value }));
 }, [cases]);

 if (byStatus.length === 0) {
 return (
 <div className="glass-card rounded-xl p-5">
 <h3 className="text-[13px] font-semibold text-foreground">{t('caseDashboardExt.typeDistribution')}</h3>
 <div className="flex flex-col items-center py-8 text-center">
 <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted/50">
 <PieChartIcon className="h-5 w-5 text-muted-foreground/50" />
 </div>
 <p className="text-sm text-muted-foreground">{t('caseDashboardExt.noData')}</p>
 </div>
 </div>
 );
 }

 const statusLabel: Record<string, string> = {
 PENDING: t('ontologyWizardExt.statusBadge.pending'),
 IN_PROGRESS: t('ontologyWizardExt.statusBadge.in_progress'),
 COMPLETED: t('ontologyWizardExt.statusBadge.complete'),
 REJECTED: t('caseDashboardExt.status.REJECTED'),
 };

 return (
 <div className="glass-card rounded-xl p-5">
 <h3 className="mb-3 text-[13px] font-semibold text-foreground">{t('caseDashboardExt.statusDistribution')}</h3>
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
