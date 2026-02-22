import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

const tabClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'font-medium text-blue-600' : 'text-neutral-600 hover:text-neutral-900';

/** 설정 페이지. 하위 탭: system, logs, users, config. */
export const SettingsPage: React.FC = () => (
  <div className="space-y-4">
    <h1 className="text-xl font-semibold">설정</h1>
    <nav className="flex gap-4 border-b border-neutral-200 pb-2">
      <NavLink to={ROUTES.SETTINGS_SYSTEM} className={tabClass}>시스템</NavLink>
      <NavLink to={ROUTES.SETTINGS_LOGS} className={tabClass}>로그</NavLink>
      <NavLink to={ROUTES.SETTINGS_USERS} className={tabClass}>사용자</NavLink>
      <NavLink to={ROUTES.SETTINGS_CONFIG} className={tabClass}>구성</NavLink>
    </nav>
    <Outlet />
  </div>
);
