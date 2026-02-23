import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

const tabClass = ({ isActive }: { isActive: boolean }) =>
  [
    'px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
    isActive
      ? 'text-primary border-primary'
      : 'text-secondary-foreground border-transparent hover:text-foreground hover:border-border',
  ].join(' ');

/** 설정 페이지. 하위 탭: system, logs, users, config. */
export const SettingsPage: React.FC = () => (
  <div className="space-y-4">
    <h1 className="text-xl font-semibold text-foreground">설정</h1>
    <nav className="flex gap-1 border-b border-border" role="tablist" aria-label="설정 메뉴">
      <NavLink to={ROUTES.SETTINGS_SYSTEM} className={tabClass} end role="tab">시스템</NavLink>
      <NavLink to={ROUTES.SETTINGS_LOGS} className={tabClass} role="tab">로그</NavLink>
      <NavLink to={ROUTES.SETTINGS_USERS} className={tabClass} role="tab">사용자</NavLink>
      <NavLink to={ROUTES.SETTINGS_CONFIG} className={tabClass} role="tab">구성</NavLink>
    </nav>
    <Outlet />
  </div>
);
