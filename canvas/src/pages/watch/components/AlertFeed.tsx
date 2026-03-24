import { useAlerts } from '@/features/watch/hooks/useAlerts';
import { useWatchStore } from '@/features/watch/store/useWatchStore';
import { useMemo } from 'react';
import { Search, BellOff } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ErrorState } from '@/shared/components/ErrorState';
import { EmptyState } from '@/shared/components/EmptyState';
import { useTranslation } from 'react-i18next';

export function AlertFeed() {
  const { t } = useTranslation();
 const { getFilteredAlerts, markAsRead, loadError, refetchAlerts } = useAlerts();
 const { filters, setSearchQuery } = useWatchStore();

 const filteredAlerts = useMemo(() => {
 return getFilteredAlerts(filters.query, filters.severity);
 }, [getFilteredAlerts, filters]);

 if (loadError) {
 return (
 <div className="flex flex-col h-full bg-card border border-border rounded-lg overflow-hidden flex-1 p-4">
 <ErrorState
 message={t('watchPage.alertLoadError', { message: loadError.message })}
 onRetry={refetchAlerts}
 />
 </div>
 );
 }

 return (
 <div className="flex flex-col h-full bg-popover border border-border rounded-lg overflow-hidden flex-1">
 <div className="p-4 border-b border-border bg-popover flex justify-between items-center">
 <h3 className="font-semibold text-foreground">{t('watchPage.msgc2d6501d')}</h3>
 <div className="relative w-64">
 <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-foreground0" />
 <Input
 type="text"
 placeholder={t('watchPage.msgc373d5d2')}
 className="pl-9 h-9 bg-card border-border text-foreground"
 value={filters.query}
 onChange={(e) => setSearchQuery(e.target.value)}
 />
 </div>
 </div>
 <div className="flex-1 overflow-y-auto p-4 space-y-3">
 {filteredAlerts.length === 0 ? (
 <EmptyState
 icon={BellOff}
 title={t('watchPage.msg035f1e51')}
 description={t('watchPage.msgddcedc69')}
 />
 ) : (
 filteredAlerts.map(alert => (
 <div
 key={alert.id}
 onClick={() => !alert.isRead && markAsRead(alert.id)}
 className={`p-4 rounded-lg border transition-all ${!alert.isRead
 ? 'bg-card border-border cursor-pointer hover:border-border'
 : 'bg-card border-border/50 opacity-70'
 }`}
 >
 <div className="flex justify-between items-start mb-2">
 <div className="flex items-center gap-2">
 {!alert.isRead && <span className="w-2 h-2 rounded-full bg-primary" />}
 <span className={`text-xs font-medium px-2 py-0.5 rounded ${alert.severity === 'critical' ? 'bg-destructive/20 text-destructive' :
 alert.severity === 'warning' ? 'bg-warning/20 text-warning' :
 'bg-primary/20 text-primary'
 }`}>
 {alert.severity.toUpperCase()}
 </span>
 </div>
 <span className="text-xs text-foreground0">
 {new Date(alert.timestamp).toLocaleString()}
 </span>
 </div>
 <h4 className={`text-sm font-semibold mb-1 ${!alert.isRead ? 'text-foreground' : 'text-muted-foreground'}`}>
 {alert.title}
 </h4>
 <p className="text-sm text-muted-foreground">
 {alert.description}
 </p>
 {alert.sourceNodeId && (
 <div className="mt-3 text-xs flex items-center gap-1.5 text-foreground0 font-mono bg-background p-1.5 rounded w-fit border border-border/50">
 {t('watchPage.relatedNode')} <span className="text-foreground/80">{alert.sourceNodeId}</span>
 </div>
 )}
 </div>
 ))
 )}
 </div>
 </div>
 );
}
