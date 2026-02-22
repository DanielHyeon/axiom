import React, { lazy, Suspense } from 'react';
import { Toaster } from 'sonner';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { RootLayout } from './layouts/RootLayout';
import { MainLayout } from './layouts/MainLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { GlobalErrorBoundary } from './components/GlobalErrorBoundary';
import { WatchToastListener } from './features/watch/components/WatchToastListener';
import { NotFoundPage } from './pages/errors/NotFoundPage';
import { ROUTES } from './lib/routes/routes';

const LoginPage = lazy(() => import('./pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const CallbackPage = lazy(() => import('./pages/auth/CallbackPage').then((m) => ({ default: m.CallbackPage })));
const CaseDashboardPage = lazy(() => import('./pages/dashboard/CaseDashboardPage').then((m) => ({ default: m.CaseDashboardPage })));
const CaseListPage = lazy(() => import('./pages/cases/CaseListPage').then((m) => ({ default: m.CaseListPage })));
const CaseDetailPage = lazy(() => import('./pages/cases/CaseDetailPage').then((m) => ({ default: m.CaseDetailPage })));
const CaseDocumentsListPage = lazy(() => import('./pages/cases/CaseDocumentsListPage').then((m) => ({ default: m.CaseDocumentsListPage })));
const CaseDocumentEditorPage = lazy(() => import('./pages/cases/CaseDocumentEditorPage').then((m) => ({ default: m.CaseDocumentEditorPage })));
const DocumentReviewPage = lazy(() => import('./pages/documents/DocumentReviewPage').then((m) => ({ default: m.DocumentReviewPage })));
const WhatIfPage = lazy(() => import('./pages/whatif/WhatIfPage').then((m) => ({ default: m.WhatIfPage })));
const OlapPivotPage = lazy(() => import('./pages/olap/OlapPivotPage').then((m) => ({ default: m.OlapPivotPage })));
const Nl2SqlPage = lazy(() => import('./pages/nl2sql/Nl2SqlPage').then((m) => ({ default: m.NL2SQLPage })));
const OntologyBrowser = lazy(() => import('./pages/ontology/OntologyBrowser').then((m) => ({ default: m.OntologyBrowser })));
const DatasourcePage = lazy(() => import('./pages/data/DatasourcePage').then((m) => ({ default: m.DatasourcePage })));
const ProcessDesignerListPage = lazy(() => import('./pages/process-designer/ProcessDesignerListPage').then((m) => ({ default: m.ProcessDesignerListPage })));
const ProcessDesignerPage = lazy(() => import('./pages/process/ProcessDesignerPage').then((m) => ({ default: m.ProcessDesignerPage })));
const WatchDashboardPage = lazy(() => import('./pages/watch/WatchDashboardPage').then((m) => ({ default: m.WatchDashboardPage })));
const SettingsPage = lazy(() => import('./pages/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const SettingsSystemPage = lazy(() => import('./pages/settings/SettingsSystemPage').then((m) => ({ default: m.SettingsSystemPage })));
const SettingsLogsPage = lazy(() => import('./pages/settings/SettingsLogsPage').then((m) => ({ default: m.SettingsLogsPage })));
const SettingsUsersPage = lazy(() => import('./pages/settings/SettingsUsersPage').then((m) => ({ default: m.SettingsUsersPage })));
const SettingsConfigPage = lazy(() => import('./pages/settings/SettingsConfigPage').then((m) => ({ default: m.SettingsConfigPage })));

function PageFallback() {
  return <div className="flex items-center justify-center p-8">로딩 중...</div>;
}

function SuspensePage({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageFallback />}>{children}</Suspense>;
}

export const App: React.FC = () => {
  return (
    <GlobalErrorBoundary>
      <Toaster richColors position="top-right" />
      <WatchToastListener />
      <BrowserRouter>
        <Routes>
          <Route element={<RootLayout />}>
            <Route path="/login" element={<Navigate to={ROUTES.AUTH.LOGIN} replace />} />
            <Route path={ROUTES.AUTH.LOGIN} element={<SuspensePage><LoginPage /></SuspensePage>} />
            <Route path={ROUTES.AUTH.CALLBACK} element={<SuspensePage><CallbackPage /></SuspensePage>} />

            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<MainLayout />}>
                <Route index element={<Navigate to={ROUTES.DASHBOARD} replace />} />
                <Route path="dashboard" element={<SuspensePage><CaseDashboardPage /></SuspensePage>} />

                <Route path="cases">
                  <Route index element={<SuspensePage><CaseListPage /></SuspensePage>} />
                  <Route path=":caseId">
                    <Route index element={<SuspensePage><CaseDetailPage /></SuspensePage>} />
                    <Route path="documents">
                      <Route index element={<SuspensePage><CaseDocumentsListPage /></SuspensePage>} />
                      <Route path=":docId" element={<SuspensePage><CaseDocumentEditorPage /></SuspensePage>} />
                      <Route path=":docId/review" element={<SuspensePage><DocumentReviewPage /></SuspensePage>} />
                    </Route>
                    <Route path="scenarios" element={<SuspensePage><WhatIfPage /></SuspensePage>} />
                  </Route>
                </Route>

                <Route path="analysis/olap" element={<SuspensePage><OlapPivotPage /></SuspensePage>} />
                <Route path="analysis/nl2sql" element={<SuspensePage><Nl2SqlPage /></SuspensePage>} />

                <Route path="data/ontology" element={<SuspensePage><OntologyBrowser /></SuspensePage>} />
                <Route path="data/datasources" element={<SuspensePage><DatasourcePage /></SuspensePage>} />

                <Route path="process-designer">
                  <Route index element={<SuspensePage><ProcessDesignerListPage /></SuspensePage>} />
                  <Route path=":boardId" element={<SuspensePage><ProcessDesignerPage /></SuspensePage>} />
                </Route>

                <Route path="watch" element={<SuspensePage><WatchDashboardPage /></SuspensePage>} />
                <Route path="settings" element={<SuspensePage><SettingsPage /></SuspensePage>}>
                  <Route index element={<Navigate to={ROUTES.SETTINGS_SYSTEM} replace />} />
                  <Route path="system" element={<SuspensePage><SettingsSystemPage /></SuspensePage>} />
                  <Route path="logs" element={<SuspensePage><SettingsLogsPage /></SuspensePage>} />
                  <Route path="users" element={<SuspensePage><SettingsUsersPage /></SuspensePage>} />
                  <Route path="config" element={<SuspensePage><SettingsConfigPage /></SuspensePage>} />
                </Route>

                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </GlobalErrorBoundary>
  );
};

export default App;
