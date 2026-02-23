import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';
import { useRole } from '@/shared/hooks/useRole';
import {
  LayoutDashboard,
  FolderKanban,
  MessageSquareText,
  BarChart3,
  Network,
  Database,
  Workflow,
  ShieldAlert,
  Settings,
} from 'lucide-react';

const navItemClass = ({ isActive }: { isActive: boolean }) =>
  [
    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-200',
    isActive
      ? 'bg-primary/15 text-primary shadow-sm shadow-primary/10'
      : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
  ].join(' ');

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-6 mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50">
      {children}
    </div>
  );
}

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const isAdmin = useRole(['admin']);
  return (
    <aside className="glass-header w-60 shrink-0 flex flex-col border-b-0 border-r border-r-[hsl(var(--sidebar-border)/0.4)]">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-blue-400 text-white text-sm font-bold shadow-lg shadow-primary/25">
          A
        </div>
        <span className="text-lg font-bold text-foreground tracking-tight">Axiom</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4 space-y-0.5">
        <NavLink to={ROUTES.DASHBOARD} className={navItemClass}>
          <LayoutDashboard className="h-4 w-4" />
          {t('nav.dashboard')}
        </NavLink>
        <NavLink to={ROUTES.CASES.LIST} className={navItemClass}>
          <FolderKanban className="h-4 w-4" />
          {t('nav.cases')}
        </NavLink>

        <SectionLabel>분석</SectionLabel>
        <NavLink to={ROUTES.ANALYSIS.NL2SQL} className={navItemClass}>
          <MessageSquareText className="h-4 w-4" />
          NL-to-SQL
        </NavLink>
        <NavLink to={ROUTES.ANALYSIS.OLAP} className={navItemClass}>
          <BarChart3 className="h-4 w-4" />
          OLAP Pivot
        </NavLink>

        <SectionLabel>데이터</SectionLabel>
        <NavLink to={ROUTES.DATA.ONTOLOGY} className={navItemClass}>
          <Network className="h-4 w-4" />
          Ontology
        </NavLink>
        <NavLink to={ROUTES.DATA.DATASOURCES} className={navItemClass}>
          <Database className="h-4 w-4" />
          {t('nav.data')}
        </NavLink>

        <SectionLabel>프로세스 &amp; 관제</SectionLabel>
        <NavLink to={ROUTES.PROCESS_DESIGNER.LIST} className={navItemClass}>
          <Workflow className="h-4 w-4" />
          {t('nav.processDesigner')}
        </NavLink>
        <NavLink to={ROUTES.WATCH} className={navItemClass}>
          <ShieldAlert className="h-4 w-4" />
          {t('nav.watch')}
        </NavLink>

        {isAdmin && (
          <>
            <SectionLabel>관리</SectionLabel>
            <NavLink to={ROUTES.SETTINGS} className={navItemClass}>
              <Settings className="h-4 w-4" />
              {t('nav.settings')}
            </NavLink>
          </>
        )}
      </nav>
    </aside>
  );
};
