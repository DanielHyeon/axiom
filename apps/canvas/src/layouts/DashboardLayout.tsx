import { Outlet, Link, useLocation } from 'react-router-dom';
import { NotificationBell } from './components/NotificationBell';

export const DashboardLayout = () => {
 const location = useLocation();

 return (
 <div className="min-h-screen bg-background text-white flex">
 {/* Sidebar Placeholder */}
 <aside className="w-64 bg-card border-r border-border flex flex-col">
 <div className="p-4 border-b border-border font-bold text-xl">
 Canvas
 </div>
 <nav className="flex-1 p-4 space-y-2">
 <Link to="/" className="block p-2 rounded hover:bg-muted transition">Dashboard</Link>
 <Link to="/documents" className="block p-2 rounded hover:bg-muted transition">Documents</Link>
 <Link to="/analysis/nl2sql" className="block p-2 rounded hover:bg-muted transition">NL2SQL Chat</Link>
 <Link to="/analysis/olap" className="block p-2 rounded hover:bg-muted transition">OLAP Pivot</Link>
 <Link to="/cases/demo/scenarios" className="block p-2 rounded hover:bg-muted transition">What-If Builder</Link>
 </nav>
 <div className="p-4 border-t border-border">
 <Link to="/login" className="block p-2 text-sm text-muted-foreground hover:text-foreground transition">Logout</Link>
 </div>
 </aside>

 {/* Main Content */}
 <main className="flex-1 flex flex-col">
 {/* Header Placeholder */}
 <header className="h-14 bg-card border-b border-border flex items-center justify-between px-6 shrink-0">
 <div className="text-sm font-medium text-muted-foreground">
 {/* Simple breadcrumb mapping for demo */}
 {location.pathname === '/' ? '대시보드' :
 location.pathname.startsWith('/ontology') ? '온톨로지 탐색' :
 location.pathname.startsWith('/watch') ? '관제 및 알람' :
 location.pathname.startsWith('/analysis/olap') ? 'OLAP 피벗 분석' : '에이리온 캔버스'}
 </div>
 <div className="flex items-center gap-4">
 <NotificationBell />
 <div className="h-8 w-8 rounded-full bg-muted border border-border overflow-hidden flex items-center justify-center">
 <span className="text-xs font-bold text-muted-foreground">AD</span>
 </div>
 </div>
 </header>

 {/* Page Content */}
 <div className="flex-1 p-6 overflow-auto">
 <Outlet />
 </div>
 </main>
 </div>
 );
};
