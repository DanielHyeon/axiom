import React from 'react';
import { Outlet } from 'react-router-dom';
import { ServiceStatusBanner } from '@/components/ServiceStatusBanner';
import { PageErrorBoundary } from '@/components/PageErrorBoundary';
import { Header } from './components/Header';
import { Sidebar } from './Sidebar';

export const MainLayout: React.FC = () => (
  <div className="relative flex flex-col h-screen bg-background text-foreground">
    <a
      href="#main-content"
      className="absolute left-4 top-4 z-[100] rounded-md bg-primary px-3 py-2 text-primary-foreground opacity-0 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      본문으로 건너뛰기
    </a>
    <ServiceStatusBanner />
    <Header />
    <div className="flex flex-1 min-h-0">
      <Sidebar />
      <main id="main-content" className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto min-w-0" tabIndex={-1}>
        <PageErrorBoundary>
          <Outlet />
        </PageErrorBoundary>
      </main>
    </div>
  </div>
);
