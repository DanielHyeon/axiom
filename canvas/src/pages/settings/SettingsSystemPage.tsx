import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { checkServiceHealth, type ServiceStatus } from '@/lib/api/health';
import { getCoreReadiness, type CoreReadinessResponse } from '@/lib/api/settingsApi';

/** 설정 > 시스템. Core health/ready 및 서비스별 헬스 연동 (읽기 전용). */
export const SettingsSystemPage: React.FC = () => {
 const { t } = useTranslation();
 const [serviceStatuses, setServiceStatuses] = useState<ServiceStatus[]>([]);
 const [coreReadiness, setCoreReadiness] = useState<CoreReadinessResponse | null>(null);
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState<string | null>(null);

 const load = useCallback(async () => {
 setLoading(true);
 setError(null);
 try {
 const [statuses, readiness] = await Promise.all([
 checkServiceHealth(),
 getCoreReadiness().catch(() => null),
 ]);
 setServiceStatuses(statuses);
 setCoreReadiness(readiness);
 } catch (e) {
 setError(e instanceof Error ? e.message : t('settingsSystem.errorLoad'));
 } finally {
 setLoading(false);
 }
 }, [t]);

 useEffect(() => {
 load();
 }, [load]);

 if (loading) {
 return (
 <div className="space-y-4">
 <h2 className="text-lg font-semibold text-foreground">{t('settingsSystem.title')}</h2>
 <p className="text-sm text-muted-foreground">{t('settingsSystem.loading')}</p>
 </div>
 );
 }

 return (
 <div className="space-y-4">
 <h2 className="text-lg font-semibold text-foreground">{t('settingsSystem.title')}</h2>
 {error && (
 <p className="text-sm text-destructive bg-red-950/30 border border-red-800 rounded px-3 py-2">
 {error}
 </p>
 )}
 <div className="space-y-3">
 <h3 className="text-sm font-medium text-foreground/80">{t('settingsSystem.serviceStatus')}</h3>
 <ul className="border border-border rounded divide-y divide-border">
 {serviceStatuses.map((s) => (
 <li key={s.name} className="px-3 md:px-4 py-2 flex items-center justify-between gap-2">
 <span className="text-foreground text-sm md:text-base">{s.name}</span>
 <span
 className={
 s.status === 'up'
 ? 'text-success font-medium'
 : 'text-destructive font-medium'
 }
 >
 {s.status === 'up' ? t('common.normal') : t('common.abnormal')}
 </span>
 </li>
 ))}
 </ul>
 </div>
 {coreReadiness && (
 <div className="space-y-3">
 <h3 className="text-sm font-medium text-foreground/80">{t('settingsSystem.coreDetail')}</h3>
 <ul className="border border-border rounded divide-y divide-border">
 {coreReadiness.checks &&
 Object.entries(coreReadiness.checks).map(([key, value]) => (
 <li key={key} className="px-3 md:px-4 py-2 flex items-center justify-between gap-2">
 <span className="text-foreground text-sm md:text-base truncate">{key}</span>
 <span
 className={
 value === 'healthy'
 ? 'text-success font-medium'
 : 'text-destructive font-medium'
 }
 >
 {value === 'healthy' ? t('common.normal') : value}
 </span>
 </li>
 ))}
 </ul>
 </div>
 )}
 <button
 type="button"
 onClick={() => load()}
 className="rounded border border-border text-foreground px-4 py-2 text-sm hover:bg-muted"
 >
 {t('common.refresh')}
 </button>
 </div>
 );
};
