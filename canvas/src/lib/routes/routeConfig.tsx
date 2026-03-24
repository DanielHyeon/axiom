import React, { Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { RootLayout } from '@/layouts/RootLayout';
import { MainLayout } from '@/layouts/MainLayout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { RoleGuard } from '@/shared/components/RoleGuard';
import { NotFoundPage } from '@/pages/errors/NotFoundPage';
import { ROUTES } from '@/lib/routes/routes';
import { lazyWithRetry } from '@/utils/lazyWithRetry';

const LoginPage = lazyWithRetry(() => import('@/pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const CallbackPage = lazyWithRetry(() => import('@/pages/auth/CallbackPage').then((m) => ({ default: m.CallbackPage })));
const CaseDashboardPage = lazyWithRetry(() => import('@/pages/dashboard/CaseDashboardPage').then((m) => ({ default: m.CaseDashboardPage })));
const CaseListPage = lazyWithRetry(() => import('@/pages/cases/CaseListPage').then((m) => ({ default: m.CaseListPage })));
const CaseDetailPage = lazyWithRetry(() => import('@/pages/cases/CaseDetailPage').then((m) => ({ default: m.CaseDetailPage })));
const CaseDocumentsListPage = lazyWithRetry(() => import('@/pages/cases/CaseDocumentsListPage').then((m) => ({ default: m.CaseDocumentsListPage })));
const CaseDocumentEditorPage = lazyWithRetry(() => import('@/pages/cases/CaseDocumentEditorPage').then((m) => ({ default: m.CaseDocumentEditorPage })));
const DocumentReviewPage = lazyWithRetry(() => import('@/pages/documents/DocumentReviewPage').then((m) => ({ default: m.DocumentReviewPage })));
const WhatIfPage = lazyWithRetry(() => import('@/pages/whatif/WhatIfPage').then((m) => ({ default: m.WhatIfPage })));
const WhatIfWizardPage = lazyWithRetry(() => import('@/pages/whatif/WhatIfWizardPage').then((m) => ({ default: m.WhatIfWizardPage })));
const OlapPivotPage = lazyWithRetry(() => import('@/pages/olap/OlapPivotPage').then((m) => ({ default: m.OlapPivotPage })));
const Nl2SqlPage = lazyWithRetry(() => import('@/pages/nl2sql/Nl2SqlPage').then((m) => ({ default: m.NL2SQLPage })));
const InsightPage = lazyWithRetry(() => import('@/pages/insight/InsightPage').then((m) => ({ default: m.InsightPage })));
const OntologyPage = lazyWithRetry(() => import('@/pages/ontology/OntologyPage').then((m) => ({ default: m.OntologyPage })));
const DatasourcePage = lazyWithRetry(() => import('@/pages/data/DatasourcePage').then((m) => ({ default: m.DatasourcePage })));
const DataIngestionPage = lazyWithRetry(() => import('@/pages/data/DataIngestionPage').then((m) => ({ default: m.DataIngestionPage })));
const DomainModelerPage = lazyWithRetry(() => import('@/pages/domain/DomainModelerPage').then((m) => ({ default: m.DomainModelerPage })));
const KineticModelerPage = lazyWithRetry(() => import('@/pages/domain/KineticModelerPage').then((m) => ({ default: m.KineticModelerPage })));
const DataQualityPage = lazyWithRetry(() => import('@/pages/data/DataQualityPage').then((m) => ({ default: m.DataQualityPage })));
const LineagePage = lazyWithRetry(() => import('@/pages/lineage/LineagePage').then((m) => ({ default: m.LineagePage })));
const ObjectExplorerPage = lazyWithRetry(() => import('@/pages/explorer/ExplorerPage').then((m) => ({ default: m.ExplorerPage })));
const GlossaryPage = lazyWithRetry(() => import('@/pages/data/GlossaryPage').then((m) => ({ default: m.GlossaryPage })));
const WorkflowEditorPage = lazyWithRetry(() => import('@/pages/workflow/WorkflowEditorPage').then((m) => ({ default: m.WorkflowEditorPage })));
// OLAP Studio 페이지 (지연 로딩 + 청크 실패 자동 재시도)
const OlapStudioPage = lazyWithRetry(() => import('@/features/olap-studio/pages/OlapStudioPage').then((m) => ({ default: m.OlapStudioPage })));
const DataSourcesPage = lazyWithRetry(() => import('@/features/olap-studio/pages/DataSourcesPage').then((m) => ({ default: m.DataSourcesPage })));
const EtlPipelinesPage = lazyWithRetry(() => import('@/features/olap-studio/pages/EtlPipelinesPage').then((m) => ({ default: m.EtlPipelinesPage })));
const CubeManagementPage = lazyWithRetry(() => import('@/features/olap-studio/pages/CubeManagementPage').then((m) => ({ default: m.CubeManagementPage })));
const SemanticCatalogPage = lazyWithRetry(() => import('@/pages/semantic-catalog/SemanticCatalogPage').then((m) => ({ default: m.SemanticCatalogPage })));
const ProcessDesignerListPage = lazyWithRetry(() => import('@/pages/process-designer/ProcessDesignerListPage').then((m) => ({ default: m.ProcessDesignerListPage })));
const ProcessDesignerPage = lazyWithRetry(() => import('@/pages/process/ProcessDesignerPage').then((m) => ({ default: m.ProcessDesignerPage })));
const WatchDashboardPage = lazyWithRetry(() => import('@/pages/watch/WatchDashboardPage').then((m) => ({ default: m.WatchDashboardPage })));
const SettingsPage = lazyWithRetry(() => import('@/pages/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const SettingsSystemPage = lazyWithRetry(() => import('@/pages/settings/SettingsSystemPage').then((m) => ({ default: m.SettingsSystemPage })));
const SettingsLogsPage = lazyWithRetry(() => import('@/pages/settings/SettingsLogsPage').then((m) => ({ default: m.SettingsLogsPage })));
const SettingsUsersPage = lazyWithRetry(() => import('@/pages/settings/SettingsUsersPage').then((m) => ({ default: m.SettingsUsersPage })));
const SettingsConfigPage = lazyWithRetry(() => import('@/pages/settings/SettingsConfigPage').then((m) => ({ default: m.SettingsConfigPage })));
const SettingsFeedbackPage = lazyWithRetry(() => import('@/pages/settings/SettingsFeedbackPage').then((m) => ({ default: m.SettingsFeedbackPage })));
const SettingsSecurityPage = lazyWithRetry(() => import('@/pages/settings/SettingsSecurityPage').then((m) => ({ default: m.SettingsSecurityPage })));

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
{ path: 'analysis/whatif/wizard', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><WhatIfWizardPage /></SuspensePage></RoleGuard> },
 { path: 'data/ontology', element: <SuspensePage><OntologyPage /></SuspensePage> },
 { path: 'data/datasources', element: <SuspensePage><DatasourcePage /></SuspensePage> },
 { path: 'data/ingestion', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><DataIngestionPage /></SuspensePage></RoleGuard> },
 { path: 'data/domain', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><DomainModelerPage /></SuspensePage></RoleGuard> },
 { path: 'data/domain/kinetic', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><KineticModelerPage /></SuspensePage></RoleGuard> },
 { path: 'data/quality', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><DataQualityPage /></SuspensePage></RoleGuard> },
{ path: 'data/lineage', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><LineagePage /></SuspensePage></RoleGuard> },
{ path: 'data/explorer', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><ObjectExplorerPage /></SuspensePage></RoleGuard> },
{ path: 'data/glossary', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><GlossaryPage /></SuspensePage></RoleGuard> },
{ path: 'data/workflow', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><WorkflowEditorPage /></SuspensePage></RoleGuard> },
// 시멘틱 카탈로그
{ path: 'data/semantic-catalog', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><SemanticCatalogPage /></SuspensePage></RoleGuard> },
// OLAP Studio 라우트
{ path: 'analysis/olap-studio', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><OlapStudioPage /></SuspensePage></RoleGuard> },
{ path: 'data/sources', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><DataSourcesPage /></SuspensePage></RoleGuard> },
{ path: 'data/etl', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><EtlPipelinesPage /></SuspensePage></RoleGuard> },
{ path: 'data/cubes', element: <RoleGuard roles={['admin', 'manager', 'analyst', 'engineer']}><SuspensePage><CubeManagementPage /></SuspensePage></RoleGuard> },
 {
 path: 'process-designer',
 children: [
 { index: true, element: <RoleGuard roles={['admin', 'manager', 'attorney', 'analyst', 'engineer', 'staff', 'viewer']}><SuspensePage><ProcessDesignerListPage /></SuspensePage></RoleGuard> },
 { path: ':boardId', element: <RoleGuard roles={['admin', 'manager', 'attorney', 'analyst', 'engineer', 'staff', 'viewer']}><SuspensePage><ProcessDesignerPage /></SuspensePage></RoleGuard> },
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
 { path: 'feedback', element: <SuspensePage><SettingsFeedbackPage /></SuspensePage> },
 { path: 'security', element: <SuspensePage><SettingsSecurityPage /></SuspensePage> },
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
