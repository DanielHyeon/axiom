import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';

const tabClass = ({ isActive }: { isActive: boolean }) =>
 [
 'px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
 isActive
 ? 'text-primary border-primary'
 : 'text-secondary-foreground border-transparent hover:text-foreground hover:border-border',
 ].join(' ');

/** 설정 페이지 — 하위 탭을 i18n으로 번역 */
export const SettingsPage: React.FC = () => {
 const { t } = useTranslation();
 return (
 <div className="space-y-4">
 <h1 className="text-xl font-semibold text-foreground">{t('settings.title')}</h1>
 <nav className="flex gap-1 border-b border-border" role="tablist" aria-label={t('settings.menuLabel')}>
 <NavLink to={ROUTES.SETTINGS_SYSTEM} className={tabClass} end role="tab">{t('settings.tabs.system')}</NavLink>
 <NavLink to={ROUTES.SETTINGS_LOGS} className={tabClass} role="tab">{t('settings.tabs.logs')}</NavLink>
 <NavLink to={ROUTES.SETTINGS_USERS} className={tabClass} role="tab">{t('settings.tabs.users')}</NavLink>
 <NavLink to={ROUTES.SETTINGS_CONFIG} className={tabClass} role="tab">{t('settings.tabs.config')}</NavLink>
 <NavLink to={ROUTES.SETTINGS_FEEDBACK} className={tabClass} role="tab">{t('settings.tabs.feedback')}</NavLink>
 <NavLink to={ROUTES.SETTINGS_SECURITY} className={tabClass} role="tab">{t('settings.tabs.security')}</NavLink>
 </nav>
 <Outlet />
 </div>
 );
};
