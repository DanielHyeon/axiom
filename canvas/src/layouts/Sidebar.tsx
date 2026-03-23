import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';
import { useRole } from '@/shared/hooks/useRole';
import {
 LayoutDashboard,
 MessageSquareText,
 BarChart3,
 Lightbulb,
 FlaskConical,
 Network,
 Database,
 Upload,
 Boxes,
 Eye,
 Workflow,
 Settings,
 ShieldCheck,
 GitBranch,
 SearchCode,
 BookOpen,
 Route,
 Library,
} from 'lucide-react';

/** H7: 사이드바 네비게이션을 그룹별로 분리 — 인지 부하 감소 */
type NavItem = { to: string; icon: React.ComponentType<{ className?: string }>; labelKey: string };
type NavGroup = { groupKey: string; items: NavItem[] };

const navGroups: NavGroup[] = [
 {
  groupKey: 'home',
  items: [
   { to: ROUTES.DASHBOARD, icon: LayoutDashboard, labelKey: 'sidebar.dashboard' },
  ],
 },
 {
  groupKey: 'analysis',
  items: [
   { to: ROUTES.ANALYSIS.NL2SQL, icon: MessageSquareText, labelKey: 'sidebar.nl2sql' },
   { to: ROUTES.ANALYSIS.OLAP, icon: BarChart3, labelKey: 'sidebar.olapPivot' },
   { to: ROUTES.ANALYSIS.INSIGHT, icon: Lightbulb, labelKey: 'sidebar.insight' },
   { to: ROUTES.ANALYSIS.WHATIF_WIZARD, icon: FlaskConical, labelKey: 'sidebar.whatif' },
  ],
 },
 {
  groupKey: 'data',
  items: [
   { to: ROUTES.DATA.ONTOLOGY, icon: Network, labelKey: 'sidebar.ontology' },
   { to: ROUTES.DATA.DATASOURCES, icon: Database, labelKey: 'sidebar.data' },
   { to: ROUTES.DATA.LINEAGE, icon: GitBranch, labelKey: 'sidebar.lineage' },
   { to: ROUTES.DATA.INGESTION, icon: Upload, labelKey: 'sidebar.ingestion' },
   { to: ROUTES.DATA.DOMAIN_MODELER, icon: Boxes, labelKey: 'sidebar.domainModeler' },
   { to: ROUTES.DATA.GLOSSARY, icon: BookOpen, labelKey: 'sidebar.glossary' },
   { to: ROUTES.DATA.SEMANTIC_CATALOG, icon: Library, labelKey: 'sidebar.semanticCatalog' },
   { to: ROUTES.DATA.QUALITY, icon: ShieldCheck, labelKey: 'sidebar.dataQuality' },
   { to: ROUTES.DATA.EXPLORER, icon: SearchCode, labelKey: 'sidebar.objectExplorer' },
  ],
 },
 {
  groupKey: 'operations',
  items: [
   { to: ROUTES.DATA.WORKFLOW_EDITOR, icon: Route, labelKey: 'sidebar.workflowEditor' },
   { to: ROUTES.PROCESS_DESIGNER.LIST, icon: Workflow, labelKey: 'sidebar.processDesigner' },
   { to: ROUTES.WATCH, icon: Eye, labelKey: 'sidebar.watch' },
  ],
 },
];

export const Sidebar: React.FC = () => {
 const { t } = useTranslation();
 const isAdmin = useRole(['admin']);

 return (
 <aside aria-label="Main navigation" className="w-16 shrink-0 flex flex-col justify-between bg-sidebar">
 {/* Top: Logo + Nav */}
 <div className="flex flex-col items-center pt-8 min-h-0 overflow-y-auto">
 {/* Logo */}
 <div className="flex items-center justify-center w-16 h-16 shrink-0">
 <span className="text-base font-bold text-sidebar-foreground">A</span>
 </div>

 {/* H7: 그룹별 네비게이션 — 구분선으로 분리 */}
 <nav className="flex flex-col w-full">
 {navGroups.map((group, gi) => (
 <div key={group.groupKey}>
  {gi > 0 && <div className="h-px bg-sidebar-border mx-3 my-1" />}
  {group.items.map((item) => (
  <NavLink
  key={item.to}
  to={item.to}
  aria-label={t(item.labelKey)}
  className={({ isActive }) =>
  `flex items-center justify-center w-16 h-12 relative group transition-colors ${
  isActive ? 'text-sidebar-foreground' : 'text-muted-foreground hover:text-foreground/60'
  }`
  }
  >
  {({ isActive }) => (
  <>
  {isActive && (
  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 bg-destructive rounded-r" />
  )}
  <item.icon className="h-[18px] w-[18px]" />
  {/* 툴팁 — 디자인 토큰 사용 */}
  <div className="absolute left-full ml-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity" role="tooltip">
  {t(item.labelKey)}
  </div>
  </>
  )}
  </NavLink>
  ))}
 </div>
 ))}
 </nav>
 </div>

 {/* Bottom: Settings */}
 <div className="flex flex-col items-center pb-4">
 {isAdmin && (
 <NavLink
 to={ROUTES.SETTINGS}
 title={t('sidebar.settings')}
 aria-label={t('sidebar.settings')}
 className={({ isActive }) =>
 `flex items-center justify-center w-16 h-16 relative group transition-colors ${
 isActive ? 'text-sidebar-foreground' : 'text-muted-foreground hover:text-foreground/60'
 }`
 }
 >
 {({ isActive }) => (
 <>
 {isActive && (
 <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 bg-destructive rounded-r" />
 )}
 <Settings className="h-[18px] w-[18px]" />
 <div className="absolute left-full ml-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity" role="tooltip">
 {t('sidebar.settings')}
 </div>
 </>
 )}
 </NavLink>
 )}
 </div>
 </aside>
 );
};
