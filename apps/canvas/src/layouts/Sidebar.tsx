import React from 'react';
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';
import { useRole } from '@/shared/hooks/useRole';

const navItemClass = ({ isActive }: { isActive: boolean }) =>
  [
    'block rounded px-2 py-2 text-sm transition-colors',
    'text-gray-700 dark:text-neutral-200',
    'hover:bg-gray-100 dark:hover:bg-neutral-800',
    isActive ? 'bg-gray-100 dark:bg-neutral-800 font-semibold' : '',
  ]
    .filter(Boolean)
    .join(' ');

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const isAdmin = useRole(['admin']);
  return (
    <aside className="w-64 bg-white dark:bg-neutral-900 shadow-md flex flex-col shrink-0">
      <div className="p-4 border-b dark:border-neutral-800">
        <h1 className="text-xl font-bold text-blue-600 dark:text-blue-400">Axiom Canvas</h1>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        <NavLink to={ROUTES.DASHBOARD} className={navItemClass}>
          📊 {t('nav.dashboard')}
        </NavLink>
        <NavLink to={ROUTES.CASES.LIST} className={navItemClass}>
          📁 {t('nav.cases')}
        </NavLink>

        <div className="mt-4 mb-1 text-xs font-semibold text-neutral-400">분석</div>
        <NavLink to={ROUTES.ANALYSIS.NL2SQL} className={navItemClass}>
          💬 NL-to-SQL
        </NavLink>
        <NavLink to={ROUTES.ANALYSIS.OLAP} className={navItemClass}>
          📈 OLAP Pivot
        </NavLink>

        <div className="mt-4 mb-1 text-xs font-semibold text-neutral-400">데이터</div>
        <NavLink to={ROUTES.DATA.ONTOLOGY} className={navItemClass}>
          🕸️ Ontology
        </NavLink>
        <NavLink to={ROUTES.DATA.DATASOURCES} className={navItemClass}>
          🔌 {t('nav.data')}
        </NavLink>

        <div className="mt-4 mb-1 text-xs font-semibold text-neutral-400">프로세스 &amp; 관제</div>
        <NavLink to={ROUTES.PROCESS_DESIGNER.LIST} className={navItemClass}>
          ⚙️ {t('nav.processDesigner')}
        </NavLink>
        <NavLink to={ROUTES.WATCH} className={navItemClass}>
          🚨 {t('nav.watch')}
        </NavLink>
        {isAdmin && (
          <>
            <div className="mt-4 mb-1 text-xs font-semibold text-neutral-400">관리</div>
            <NavLink to={ROUTES.SETTINGS} className={navItemClass}>
              ⚙ {t('nav.settings')}
            </NavLink>
          </>
        )}
      </nav>
    </aside>
  );
};
