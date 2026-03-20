// features/insight/components/KpiSelector.tsx
// KPI selector — fetches KPI list from API, falls back to manual input

import { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Zap } from 'lucide-react';
import { fetchKpis } from '../api/insightApi';
import type { KpiListItem } from '../types/insight';

interface KpiSelectorProps {
 onSelect: (kpiId: string, fingerprint: string) => void;
 loading?: boolean;
}

export function KpiSelector({ onSelect, loading }: KpiSelectorProps) {
 const { t } = useTranslation();
 const [inputValue, setInputValue] = useState('');
 const [kpis, setKpis] = useState<KpiListItem[]>([]);
 const [kpisLoading, setKpisLoading] = useState(true);

 useEffect(() => {
 setKpisLoading(true);
 fetchKpis({ limit: 10 })
 .then((res) => setKpis(res.kpis))
 .catch((err: unknown) => {
   const msg = err instanceof Error ? err.message : '알 수 없는 오류';
   toast.error('KPI 목록을 불러오지 못했습니다', { description: msg });
   setKpis([]);
 })
 .finally(() => setKpisLoading(false));
 }, []);

 const handleSubmit = useCallback(
 (e: React.FormEvent) => {
 e.preventDefault();
 const trimmed = inputValue.trim();
 if (trimmed) {
 onSelect(trimmed, trimmed);
 }
 },
 [inputValue, onSelect],
 );

 const handleQuickSelect = useCallback(
 (kpi: KpiListItem) => {
 setInputValue(kpi.fingerprint);
 onSelect(kpi.id, kpi.fingerprint);
 },
 [onSelect],
 );

 return (
 <div className="space-y-3">
 <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
 <Search className="h-3 w-3" />
 {t('insight.kpiSelector.title')}
 </div>

 <form onSubmit={handleSubmit} className="flex gap-2">
 <Input
 value={inputValue}
 onChange={(e) => setInputValue(e.target.value)}
 placeholder={t('insight.kpiSelector.placeholder')}
 className="h-8 text-xs bg-muted/50 border-border"
 disabled={loading}
 />
 <Button
 type="submit"
 size="sm"
 className="h-8 px-3 text-xs shrink-0"
 disabled={!inputValue.trim() || loading}
 >
 <Zap className="h-3 w-3 mr-1" />
 {t('insight.kpiSelector.analyze')}
 </Button>
 </form>

 <div className="space-y-1">
 <div className="text-[10px] font-medium text-foreground0 uppercase tracking-wider">
 {kpisLoading ? t('insight.kpiSelector.loading') : kpis.length > 0 ? t('insight.kpiSelector.recentKpis') : t('insight.kpiSelector.noKpis')}
 </div>
 {kpis.length > 0 && (
 <div className="flex flex-wrap gap-1">
 {kpis.map((kpi) => (
 <button
 key={kpi.id}
 type="button"
 onClick={() => handleQuickSelect(kpi)}
 disabled={loading}
 className="rounded-full border border-border bg-muted/30 px-2.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary hover:bg-primary/10 disabled:opacity-50"
 >
 {kpi.name}
 </button>
 ))}
 </div>
 )}
 </div>
 </div>
 );
}
