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
 Boxes,
 Eye,
 Workflow,
 Settings,
} from 'lucide-react';

/** 사이드바 네비게이션 아이템 — i18n 키를 labelKey로 사용 */
const navItems = [
 { to: ROUTES.DASHBOARD, icon: LayoutDashboard, labelKey: 'sidebar.dashboard' },
 { to: ROUTES.ANALYSIS.NL2SQL, icon: MessageSquareText, labelKey: 'sidebar.nl2sql' },
 { to: ROUTES.ANALYSIS.OLAP, icon: BarChart3, labelKey: 'sidebar.olapPivot' },
 { to: ROUTES.ANALYSIS.INSIGHT, icon: Lightbulb, labelKey: 'sidebar.insight' },
 { to: ROUTES.ANALYSIS.WHATIF_WIZARD, icon: FlaskConical, labelKey: 'sidebar.whatif' },
 { to: ROUTES.DATA.ONTOLOGY, icon: Network, labelKey: 'sidebar.ontology' },
 { to: ROUTES.DATA.DATASOURCES, icon: Database, labelKey: 'sidebar.data' },
 { to: ROUTES.DATA.DOMAIN_MODELER, icon: Boxes, labelKey: 'sidebar.domainModeler' },
 { to: ROUTES.PROCESS_DESIGNER.LIST, icon: Workflow, labelKey: 'sidebar.processDesigner' },
 { to: ROUTES.WATCH, icon: Eye, labelKey: 'sidebar.watch' },
];

export const Sidebar: React.FC = () => {
 const { t } = useTranslation();
 const isAdmin = useRole(['admin']);

 return (
 <aside className="w-16 shrink-0 flex flex-col justify-between bg-sidebar">
 {/* Top: Logo + Nav */}
 <div className="flex flex-col items-center pt-8 min-h-0 overflow-y-auto">
 {/* Logo */}
 <div className="flex items-center justify-center w-16 h-16 shrink-0">
 <span className="text-base font-bold text-sidebar-foreground font-[Sora]">A</span>
 </div>

 {/* Nav items */}
 <nav className="flex flex-col w-full">
 {navItems.map((item) => (
 <NavLink
 key={item.to}
 to={item.to}
 title={t(item.labelKey)}
 aria-label={t(item.labelKey)}
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
 <item.icon className="h-[18px] w-[18px]" />
 {/* Tooltip — 번역된 라벨 표시 */}
 <div className="absolute left-full ml-2 px-2 py-1 bg-zinc-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity">
 {t(item.labelKey)}
 </div>
 </>
 )}
 </NavLink>
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
 <div className="absolute left-full ml-2 px-2 py-1 bg-zinc-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity">
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
