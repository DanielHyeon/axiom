import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { useCaseStats } from '@/features/case-dashboard/hooks/useCaseStats';
import { useCaseActivities } from '@/features/case-dashboard/hooks/useCaseActivities';
import { useDashboardConfig } from '@/features/case-dashboard/hooks/useDashboardConfig';
import { StatsCard } from '@/features/case-dashboard/components/StatsCard';
import { RoleGreeting } from '@/features/case-dashboard/components/RoleGreeting';
import { QuickActionsPanel } from '@/features/case-dashboard/components/QuickActionsPanel';
import { DashboardComposer } from '@/features/case-dashboard/components/DashboardComposer';
import { CaseTable } from '@/features/case-dashboard/components/CaseTable';
import { CaseFilters, type CaseStatusFilter, type CaseTypeFilter } from '@/features/case-dashboard/components/CaseFilters';
import { CaseTimeline } from '@/features/case-dashboard/components/CaseTimeline';
import { CaseDistributionChart } from '@/features/case-dashboard/components/CaseDistributionChart';
import { ErrorState } from '@/shared/components/ErrorState';
import { CardGridSkeleton, TableRowsSkeleton } from '@/shared/components/ListSkeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { FolderOpen } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useNavigate, Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

export function CaseDashboardPage() {
 const { t } = useTranslation();
 const [statusFilter, setStatusFilter] = useState<CaseStatusFilter>('ALL');
 const [typeFilter, setTypeFilter] = useState<CaseTypeFilter>('ALL');
 const [searchQuery, setSearchQuery] = useState('');
 const { data: cases, isLoading, error, refetch: refetchCases } = useCases();
 const { data: activities = [] } = useCaseActivities(20);
 const filteredCases = useMemo(() => {
 if (!cases) return [];
 let list = cases;
 if (statusFilter !== 'ALL') list = list.filter((c) => c.status === statusFilter);
 if (typeFilter !== 'ALL') list = list.filter((c) => c.priority === typeFilter);
 if (searchQuery.trim()) {
 const q = searchQuery.trim().toLowerCase();
 list = list.filter((c) => c.title.toLowerCase().includes(q));
 }
 return list;
 }, [cases, statusFilter, typeFilter, searchQuery]);
 const stats = useCaseStats(cases);
 const userEmail = useAuthStore((s) => s.user?.email);
 const role = useAuthStore((s) => s.user?.role);
 const panels = useDashboardConfig(role);
 const navigate = useNavigate();

 if (error) {
 return (
 <div className="p-4 md:p-6 lg:p-8">
 <ErrorState message={t('dashboard.errorLoadCases', { message: error.message })} onRetry={refetchCases} />
 </div>
 );
 }

 return (
 <div className="p-4 md:p-6 lg:p-8">
 <RoleGreeting
 userName={userEmail}
 role={role}
 workCount={stats.inReview}
 />

 <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
 {isLoading ? (
 <CardGridSkeleton count={4} />
 ) : (
 <>
 <StatsCard label={t('dashboard.allCases')} value={stats.total} trend="same" trendLabel={t('common.comparedToYesterday')} />
 <StatsCard label={t('dashboard.inProgress')} value={stats.inProgress} trend="same" trendLabel={t('common.comparedToYesterday')} />
 <StatsCard label={t('dashboard.inReview')} value={stats.inReview} trend="same" trendLabel={t('common.comparedToYesterday')} />
 <StatsCard label={t('dashboard.dueThisWeek')} value={stats.dueThisWeek} trend="same" trendLabel={t('common.comparedToYesterday')} />
 </>
 )}
 </div>

 <div className="mb-4">
 <CaseFilters
 status={statusFilter}
 onStatusChange={setStatusFilter}
 type={typeFilter}
 onTypeChange={setTypeFilter}
 searchQuery={searchQuery}
 onSearchQueryChange={setSearchQuery}
 />
 </div>

 <div className="mb-6">
 <QuickActionsPanel />
 </div>

 {/* 역할별 패널 — DashboardComposer가 useDashboardConfig 기반으로 조합 */}
 <div className="mb-6 grid grid-cols-1 gap-4 md:gap-6 lg:grid-cols-3">
 <div className="lg:col-span-2">
  <DashboardComposer panels={panels} />
 </div>
 <div className="space-y-4">
 <CaseTimeline items={activities} />
 <CaseDistributionChart cases={filteredCases} />
 </div>
 </div>

 <div>
 <div className="mb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
 <h2 className="text-base md:text-lg font-semibold text-foreground">{t('dashboard.caseSummary')}</h2>
 <Link
 to={ROUTES.CASES.LIST}
 className="text-sm text-primary hover:underline"
 >
 {t('common.viewAll')}
 </Link>
 </div>
 {isLoading ? (
 <TableRowsSkeleton rows={5} />
 ) : filteredCases.length === 0 ? (
 <EmptyState
 icon={FolderOpen}
 title={t('dashboard.noCases')}
 description={t('dashboard.noCasesDesc')}
 actionLabel={t('dashboard.viewCaseList')}
 onAction={() => navigate(ROUTES.CASES.LIST)}
 />
 ) : (
 <CaseTable data={filteredCases.slice(0, 5)} />
 )}
 </div>
 </div>
 );
}
