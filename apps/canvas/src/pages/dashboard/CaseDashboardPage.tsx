import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { useCaseStats } from '@/features/case-dashboard/hooks/useCaseStats';
import { useCaseActivities } from '@/features/case-dashboard/hooks/useCaseActivities';
import { useDashboardConfig } from '@/features/case-dashboard/hooks/useDashboardConfig';
import { StatsCard } from '@/features/case-dashboard/components/StatsCard';
import { RoleGreeting } from '@/features/case-dashboard/components/RoleGreeting';
import { QuickActionsPanel } from '@/features/case-dashboard/components/QuickActionsPanel';
import { MyWorkitemsPanel } from '@/features/case-dashboard/components/MyWorkitemsPanel';
import { ApprovalQueuePanel } from '@/features/case-dashboard/components/ApprovalQueuePanel';
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
  const role = useAuthStore((s) => s.user?.role);
  const panels = useDashboardConfig(role);
  const showMyWorkitems = panels.includes('myWorkitems');
  const showApprovalQueue = panels.includes('approvalQueue');
  const navigate = useNavigate();

  if (error) {
    return (
      <div className="p-6">
        <ErrorState message={`케이스 목록을 불러올 수 없습니다. ${error.message}`} onRetry={refetchCases} />
      </div>
    );
  }

  return (
    <div className="p-6">
      <RoleGreeting
        userName={useAuthStore((s) => s.user?.email)}
        role={role}
        workCount={stats.inReview}
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          <CardGridSkeleton count={4} />
        ) : (
          <>
            <StatsCard label={t('dashboard.allCases')} value={stats.total} trend="same" trendLabel="전일 대비" />
            <StatsCard label={t('dashboard.inProgress')} value={stats.inProgress} trend="same" trendLabel="전일 대비" />
            <StatsCard label={t('dashboard.inReview')} value={stats.inReview} trend="same" trendLabel="전일 대비" />
            <StatsCard label={t('dashboard.dueThisWeek')} value={stats.dueThisWeek} trend="same" trendLabel="전일 대비" />
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

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {(showMyWorkitems || showApprovalQueue) && (
          <div className="space-y-4 lg:col-span-2">
            {showMyWorkitems && <MyWorkitemsPanel />}
            {showApprovalQueue && <ApprovalQueuePanel />}
          </div>
        )}
        <div className="space-y-4">
          <CaseTimeline items={activities} />
          <CaseDistributionChart cases={filteredCases} />
        </div>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">{t('dashboard.caseSummary')}</h2>
          <Link
            to={ROUTES.CASES.LIST}
            className="text-sm text-primary hover:underline"
          >
            전체 보기
          </Link>
        </div>
        {isLoading ? (
          <TableRowsSkeleton rows={5} />
        ) : filteredCases.length === 0 ? (
          <EmptyState
            icon={FolderOpen}
            title="케이스가 없습니다"
            description="등록된 케이스가 없거나 필터 조건에 맞는 케이스가 없습니다."
            actionLabel="케이스 목록 보기"
            onAction={() => navigate(ROUTES.CASES.LIST)}
          />
        ) : (
          <CaseTable data={filteredCases.slice(0, 5)} />
        )}
      </div>
    </div>
  );
}
