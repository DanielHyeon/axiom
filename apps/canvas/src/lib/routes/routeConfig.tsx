import React, { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { RootLayout } from '@/layouts/RootLayout';
import { MainLayout } from '@/layouts/MainLayout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { RoleGuard } from '@/shared/components/RoleGuard';
import { NotFoundPage } from '@/pages/errors/NotFoundPage';
import { ROUTES } from '@/lib/routes/routes';

const LoginPage = lazy(() => import('@/pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const CallbackPage = lazy(() => import('@/pages/auth/CallbackPage').then((m) => ({ default: m.CallbackPage })));
const CaseDashboardPage = lazy(() => import('@/pages/dashboard/CaseDashboardPage').then((m) => ({ default: m.CaseDashboardPage })));
const CaseListPage = lazy(() => import('@/pages/cases/CaseListPage').then((m) => ({ default: m.CaseListPage })));
const CaseDetailPage = lazy(() => import('@/pages/cases/CaseDetailPage').then((m) => ({ default: m.CaseDetailPage })));
const CaseDocumentsListPage = lazy(() => import('@/pages/cases/CaseDocumentsListPage').then((m) => ({ default: m.CaseDocumentsListPage })));
const CaseDocumentEditorPage = lazy(() => import('@/pages/cases/CaseDocumentEditorPage').then((m) => ({ default: m.CaseDocumentEditorPage })));
const DocumentReviewPage = lazy(() => import('@/pages/documents/DocumentReviewPage').then((m) => ({ default: m.DocumentReviewPage })));
const WhatIfPage = lazy(() => import('@/pages/whatif/WhatIfPage').then((m) => ({ default: m.WhatIfPage })));
const OlapPivotPage = lazy(() => import('@/pages/olap/OlapPivotPage').then((m) => ({ default: m.OlapPivotPage })));
const Nl2SqlPage = lazy(() => import('@/pages/nl2sql/Nl2SqlPage').then((m) => ({ default: m.NL2SQLPage })));
const InsightPage = lazy(() => import('@/pages/insight/InsightPage').then((m) => ({ default: m.InsightPage })));
const OntologyPage = lazy(() => import('@/pages/ontology/OntologyPage').then((m) => ({ default: m.OntologyPage })));
const DatasourcePage = lazy(() => import('@/pages/data/DatasourcePage').then((m) => ({ default: m.DatasourcePage })));
const ProcessDesignerListPage = lazy(() => import('@/pages/process-designer/ProcessDesignerListPage').then((m) => ({ default: m.ProcessDesignerListPage })));
const ProcessDesignerPage = lazy(() => import('@/pages/process/ProcessDesignerPage').then((m) => ({ default: m.ProcessDesignerPage })));
const WatchDashboardPage = lazy(() => import('@/pages/watch/WatchDashboardPage').then((m) => ({ default: m.WatchDashboardPage })));
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const SettingsSystemPage = lazy(() => import('@/pages/settings/SettingsSystemPage').then((m) => ({ default: m.SettingsSystemPage })));
const SettingsLogsPage = lazy(() => import('@/pages/settings/SettingsLogsPage').then((m) => ({ default: m.SettingsLogsPage })));
const SettingsUsersPage = lazy(() => import('@/pages/settings/SettingsUsersPage').then((m) => ({ default: m.SettingsUsersPage })));
const SettingsConfigPage = lazy(() => import('@/pages/settings/SettingsConfigPage').then((m) => ({ default: m.SettingsConfigPage })));

function PageFallback() {
  const { t } = useTranslation();
  return <div className="flex items-center justify-center p-8">{t('common.loading')}</div>;
}

function SuspensePage({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageFallback />}>{children}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { path: 'login', element: <Navigate to={ROUTES.AUTH.LOGIN} replace /> },
      { path: 'auth/login', element: <SuspensePage><LoginPage /></SuspensePage> },
      { path: 'auth/callback', element: <SuspensePage><CallbackPage /></SuspensePage> },
      {
        element: <ProtectedRoute />,
        children: [
          {
            element: <MainLayout />,
            children: [
              { index: true, element: <Navigate to={ROUTES.DASHBOARD} replace /> },
              { path: 'dashboard', element: <SuspensePage><CaseDashboardPage /></SuspensePage> },
              {
                path: 'cases',
                children: [
                  { index: true, element: <SuspensePage><CaseListPage /></SuspensePage> },
                  {
                    path: ':caseId',
                    children: [
                      { index: true, element: <SuspensePage><CaseDetailPage /></SuspensePage> },
                      {
                        path: 'documents',
                        children: [
                          { index: true, element: <SuspensePage><CaseDocumentsListPage /></SuspensePage> },
                          { path: ':docId', element: <SuspensePage><CaseDocumentEditorPage /></SuspensePage> },
                          { path: ':docId/review', element: <SuspensePage><DocumentReviewPage /></SuspensePage> },
                        ],
                      },
                      { path: 'scenarios', element: <SuspensePage><WhatIfPage /></SuspensePage> },
                    ],
                  },
                ],
              },
              { path: 'analysis/olap', element: <SuspensePage><OlapPivotPage /></SuspensePage> },
              { path: 'analysis/nl2sql', element: <RoleGuard roles={['admin', 'manager', 'attorney', 'analyst', 'engineer']}><SuspensePage><Nl2SqlPage /></SuspensePage></RoleGuard> },
              { path: 'analysis/insight', element: <RoleGuard roles={['admin', 'manager', 'attorney', 'analyst', 'engineer']}><SuspensePage><InsightPage /></SuspensePage></RoleGuard> },
              { path: 'data/ontology', element: <SuspensePage><OntologyPage /></SuspensePage> },
              { path: 'data/datasources', element: <SuspensePage><DatasourcePage /></SuspensePage> },
              {
                path: 'process-designer',
                children: [
                  { index: true, element: <SuspensePage><ProcessDesignerListPage /></SuspensePage> },
                  { path: ':boardId', element: <SuspensePage><ProcessDesignerPage /></SuspensePage> },
                ],
              },
              { path: 'watch', element: <SuspensePage><WatchDashboardPage /></SuspensePage> },
              {
                path: 'settings',
                element: (
                  <RoleGuard roles={['admin']}>
                    <SuspensePage><SettingsPage /></SuspensePage>
                  </RoleGuard>
                ),
                children: [
                  { index: true, element: <Navigate to={ROUTES.SETTINGS_SYSTEM} replace /> },
                  { path: 'system', element: <SuspensePage><SettingsSystemPage /></SuspensePage> },
                  { path: 'logs', element: <SuspensePage><SettingsLogsPage /></SuspensePage> },
                  { path: 'users', element: <SuspensePage><SettingsUsersPage /></SuspensePage> },
                  { path: 'config', element: <SuspensePage><SettingsConfigPage /></SuspensePage> },
                ],
              },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
]);
