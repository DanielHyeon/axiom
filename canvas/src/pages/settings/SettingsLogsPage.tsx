import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

type LogTab = 'explorer' | 'ai-analysis';

/** 설정 > 로그. 탭: Explorer(시스템/앱 로그), AI 분석 로그. 추후 로그 API 연동. */
export const SettingsLogsPage: React.FC = () => {
 const { t } = useTranslation();
 const [tab, setTab] = useState<LogTab>('explorer');
 return (
 <div className="space-y-4">
 <h2 className="text-base md:text-lg font-semibold text-foreground">{t('settingsLogs.title')}</h2>
 <div className="flex gap-1 border-b border-border overflow-x-auto" role="tablist" aria-label={t('settingsLogs.tabLabel')}>
 <button
 type="button"
 role="tab"
 aria-label={t('settingsLogs.explorerLabel')}
 onClick={() => setTab('explorer')}
 className={`px-2.5 md:px-3 py-2 text-xs md:text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${tab === 'explorer' ? 'border-primary text-primary' : 'border-transparent text-secondary-foreground hover:text-foreground hover:border-border'}`}
 >
 {t('settingsLogs.explorer')}
 </button>
 <button
 type="button"
 role="tab"
 aria-label={t('settingsLogs.aiAnalysisLabel')}
 onClick={() => setTab('ai-analysis')}
 className={`px-2.5 md:px-3 py-2 text-xs md:text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${tab === 'ai-analysis' ? 'border-primary text-primary' : 'border-transparent text-secondary-foreground hover:text-foreground hover:border-border'}`}
 >
 {t('settingsLogs.aiAnalysis')}
 </button>
 </div>
 {tab === 'explorer' && (
 <p className="text-sm text-secondary-foreground">{t('settingsLogs.explorerPlaceholder')}</p>
 )}
 {tab === 'ai-analysis' && (
 <p className="text-sm text-secondary-foreground">{t('settingsLogs.aiAnalysisPlaceholder')}</p>
 )}
 </div>
 );
};
