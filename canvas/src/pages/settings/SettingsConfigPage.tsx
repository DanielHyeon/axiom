import React from 'react';
import { useTranslation } from 'react-i18next';

/** 설정 > 구성. 환경·기능 설정. 추후 설정 API 연동. */
export const SettingsConfigPage: React.FC = () => {
 const { t } = useTranslation();
 return (
 <div className="space-y-4">
 <h2 className="text-lg font-semibold text-foreground">{t('settingsConfig.title')}</h2>
 <p className="text-sm text-muted-foreground">{t('settingsConfig.placeholder')}</p>
 </div>
 );
};
