import { Outlet, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { NotificationBell } from './components/NotificationBell';

export const DashboardLayout = () => {
 const location = useLocation();
 const { t } = useTranslation();

 return (
 <div className="min-h-screen bg-background text-primary-foreground flex flex-col md:flex-row">
 {/* Sidebar Placeholder */}
 <aside className="w-full md:w-64 bg-card border-b md:border-b-0 md:border-r border-border flex flex-row md:flex-col overflow-x-auto md:overflow-x-visible">
 <div className="p-3 md:p-4 border-b border-border font-bold text-lg md:text-xl shrink-0 hidden md:block">
 Canvas
 </div>
 <nav className="flex flex-row md:flex-col flex-1 p-2 md:p-4 gap-1 md:space-y-2">
 <Link to="/" className="block p-2 rounded hover:bg-muted transition whitespace-nowrap text-sm">Dashboard</Link>
 <Link to="/documents" className="block p-2 rounded hover:bg-muted transition whitespace-nowrap text-sm">Documents</Link>
 <Link to="/analysis/nl2sql" className="block p-2 rounded hover:bg-muted transition whitespace-nowrap text-sm">NL2SQL Chat</Link>
 <Link to="/analysis/olap" className="block p-2 rounded hover:bg-muted transition whitespace-nowrap text-sm">OLAP Pivot</Link>
 <Link to="/cases/demo/scenarios" className="block p-2 rounded hover:bg-muted transition whitespace-nowrap text-sm">What-If Builder</Link>
 </nav>
 <div className="p-2 md:p-4 md:border-t border-border hidden md:block">
 <Link to="/login" className="block p-2 text-sm text-muted-foreground hover:text-foreground transition">Logout</Link>
 </div>
 </aside>

 {/* Main Content */}
 <main className="flex-1 flex flex-col min-w-0">
 {/* Header Placeholder */}
 <header className="h-12 md:h-14 bg-card border-b border-border flex items-center justify-between px-4 md:px-6 shrink-0">
 <div className="text-xs md:text-sm font-medium text-muted-foreground truncate">
 {location.pathname === '/' ? t('breadcrumb.dashboard') :
 location.pathname.startsWith('/ontology') ? t('breadcrumb.ontology') :
 location.pathname.startsWith('/watch') ? t('breadcrumb.watch') :
 location.pathname.startsWith('/analysis/olap') ? t('breadcrumb.olapPivot') : t('breadcrumb.default')}
 </div>
 <div className="flex items-center gap-2 md:gap-4 shrink-0">
 <NotificationBell />
 <div className="h-7 w-7 md:h-8 md:w-8 rounded-full bg-muted border border-border overflow-hidden flex items-center justify-center">
 <span className="text-xs font-bold text-muted-foreground">AD</span>
 </div>
 </div>
 </header>

 {/* Page Content */}
 <div className="flex-1 p-4 md:p-6 overflow-auto">
 <Outlet />
 </div>
 </main>
 </div>
 );
};
