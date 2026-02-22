import React from 'react';
import { Outlet } from 'react-router-dom';
import { ServiceStatusBanner } from '@/components/ServiceStatusBanner';
import { PageErrorBoundary } from '@/components/PageErrorBoundary';
import { Header } from './components/Header';
import { Sidebar } from './Sidebar';

export const MainLayout: React.FC = () => (
  <div className="flex flex-col h-screen bg-gray-50">
    <ServiceStatusBanner />
    <Header />
    <div className="flex flex-1 min-h-0">
      <Sidebar />
      <main className="flex-1 p-8 overflow-auto min-w-0">
        <PageErrorBoundary>
          <Outlet />
        </PageErrorBoundary>
      </main>
    </div>
  </div>
);
