import { Outlet } from 'react-router-dom';
import { ServiceStatusBanner } from '@/components/ServiceStatusBanner';
import { PageErrorBoundary } from '@/components/PageErrorBoundary';
import { Sidebar } from './Sidebar';
import { PageTabHeader } from './components/PageTabHeader';

export const MainLayout: React.FC = () => (
  <div className="flex h-screen bg-[#FAFAFA] overflow-hidden">
    <Sidebar />
    <div className="flex-1 flex flex-col min-w-0">
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
