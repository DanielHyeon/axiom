import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { GlobalErrorBoundary } from './components/GlobalErrorBoundary';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { NL2SQLPage } from './pages/nl2sql/Nl2SqlPage';
import { ProcessDesigner } from './pages/process/ProcessDesigner';
import { DocumentManager } from './pages/documents/DocumentManager';
import { OlapPivot } from './pages/analytics/OlapPivot';
import { WhatIfBuilder } from './pages/analytics/WhatIfBuilder';
import { OntologyBrowser } from './pages/ontology/OntologyBrowser';
import { WatchAlerts } from './pages/watch/WatchAlerts';
import { LoginPage } from './pages/auth/LoginPage';

export const App: React.FC = () => {
  return (
    <GlobalErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          {/* Wrapping MVP inside Auth Interceptor */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<MainLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="nl2sql" element={<NL2SQLPage />} />
              <Route path="process" element={<ProcessDesigner />} />
              <Route path="documents" element={<DocumentManager />} />

              <Route path="analytics/pivot" element={<OlapPivot />} />
              <Route path="analytics/what-if" element={<WhatIfBuilder />} />

              <Route path="ontology" element={<OntologyBrowser />} />
              <Route path="watch" element={<WatchAlerts />} />

              <Route path="*" element={<div>Page Not Found</div>} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </GlobalErrorBoundary>
  );
};

export default App;
