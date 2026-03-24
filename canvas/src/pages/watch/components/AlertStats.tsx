import { useTranslation } from 'react-i18next';
export function AlertStats() {
  const { t } = useTranslation();
 return (
 <div className="grid grid-cols-4 gap-4 mb-6">
 <div className="bg-popover border border-border rounded-lg p-5">
 <div className="text-muted-foreground text-sm font-medium mb-1">{t('watchPage.msg1cd87e14')}</div>
 <div className="text-2xl font-bold text-foreground">1,204</div>
 <div className="text-xs text-foreground0 mt-2">+12% from yesterday</div>
 </div>
 <div className="bg-popover border border-red-900/50 rounded-lg p-5">
 <div className="text-destructive text-sm font-medium mb-1">{t('watchPage.msg726e3a56')}</div>
 <div className="text-2xl font-bold text-destructive">28</div>
 <div className="text-xs text-destructive/70 mt-2">{t('watchPage.msg87994e69')}</div>
 </div>
 <div className="bg-popover border border-amber-900/50 rounded-lg p-5">
 <div className="text-warning text-sm font-medium mb-1">{t('watchPage.msg778211bf')}</div>
 <div className="text-2xl font-bold text-warning">142</div>
 <div className="text-xs text-warning/70 mt-2">{t('watchPage.msg431d64e1')}</div>
 </div>
 <div className="bg-popover border border-blue-900/50 rounded-lg p-5">
 <div className="text-primary text-sm font-medium mb-1">{t('watchPage.msg86befdde')}</div>
 <div className="text-2xl font-bold text-primary">1,034</div>
 <div className="text-xs text-primary/70 mt-2">{t('watchPage.msg10cffb08')}</div>
 </div>
 </div>
 );
}
