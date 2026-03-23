import { Outlet } from 'react-router-dom';
import { ServiceStatusBanner } from '@/components/ServiceStatusBanner';
import { PageErrorBoundary } from '@/components/PageErrorBoundary';
import { Sidebar } from './Sidebar';
import { PageTabHeader } from './components/PageTabHeader';

export const MainLayout: React.FC = () => (
 <div className="flex h-screen bg-background overflow-hidden">
 {/* C2: Skip navigation — 키보드 사용자가 사이드바 건너뛰기 (WCAG 2.4.1) */}
 <a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground focus:text-sm focus:font-medium focus:shadow-lg"
 >
  Skip to main content
 </a>
 <Sidebar />
 <div className="flex-1 flex flex-col min-w-0 w-full md:w-auto">
 <ServiceStatusBanner />
 <PageTabHeader />
 <main id="main-content" className="flex-1 overflow-hidden min-w-0" tabIndex={-1}>
 <PageErrorBoundary>
 <Outlet />
 </PageErrorBoundary>
 </main>
 </div>
 </div>
);
