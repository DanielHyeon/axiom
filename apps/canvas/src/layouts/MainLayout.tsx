import { Outlet } from 'react-router-dom';
import { ServiceStatusBanner } from '@/components/ServiceStatusBanner';
import { PageErrorBoundary } from '@/components/PageErrorBoundary';
import { Header } from './components/Header';
import { Sidebar } from './Sidebar';

export const MainLayout: React.FC = () => (
  <div className="relative flex flex-col h-screen bg-background text-foreground overflow-hidden">
    {/* Ambient gradient blobs for depth */}
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute -top-[40%] -left-[20%] h-[80%] w-[60%] rounded-full bg-primary/5 blur-3xl" />
      <div className="absolute -bottom-[30%] -right-[15%] h-[70%] w-[50%] rounded-full bg-primary/3 blur-3xl" />
    </div>

    <a
      href="#main-content"
      className="absolute left-4 top-4 z-[100] rounded-md bg-primary px-3 py-2 text-primary-foreground opacity-0 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      본문으로 건너뛰기
    </a>
    <ServiceStatusBanner />
    <Header />
    <div className="relative flex flex-1 min-h-0">
      <Sidebar />
      <main id="main-content" className="flex-1 overflow-auto min-w-0" tabIndex={-1}>
        <PageErrorBoundary>
          <Outlet />
        </PageErrorBoundary>
      </main>
    </div>
  </div>
);
