import { useMemo, useState } from 'react';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { useCaseStats } from '@/features/case-dashboard/hooks/useCaseStats';
import { useDashboardConfig } from '@/features/case-dashboard/hooks/useDashboardConfig';
import { StatsCard } from '@/features/case-dashboard/components/StatsCard';
import { RoleGreeting } from '@/features/case-dashboard/components/RoleGreeting';
import { QuickActionsPanel } from '@/features/case-dashboard/components/QuickActionsPanel';
import { MyWorkitemsPanel } from '@/features/case-dashboard/components/MyWorkitemsPanel';
import { ApprovalQueuePanel } from '@/features/case-dashboard/components/ApprovalQueuePanel';
import { CaseTable } from '@/features/case-dashboard/components/CaseTable';
import { CaseFilters, type CaseStatusFilter } from '@/features/case-dashboard/components/CaseFilters';
import { CaseTimeline } from '@/features/case-dashboard/components/CaseTimeline';
import { CaseDistributionChart } from '@/features/case-dashboard/components/CaseDistributionChart';
import { useAuthStore } from '@/stores/authStore';

export function CaseDashboardPage() {
  const [statusFilter, setStatusFilter] = useState<CaseStatusFilter>('ALL');
  const { data: cases, isLoading, error } = useCases();
  const filteredCases = useMemo(() => {
    if (!cases) return [];
    if (statusFilter === 'ALL') return cases;
    return cases.filter((c) => c.status === statusFilter);
  }, [cases, statusFilter]);
  const stats = useCaseStats(cases);
  const role = useAuthStore((s) => s.user?.role);
  const panels = useDashboardConfig(role);
  const showMyWorkitems = panels.includes('myWorkitems');
  const showApprovalQueue = panels.includes('approvalQueue');

  return (
    <div className="p-6">
      <RoleGreeting
        userName={useAuthStore((s) => s.user?.email)}
        role={role}
        workCount={stats.inReview}
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard label="전체 케이스" value={stats.total} />
        <StatsCard label="진행 중" value={stats.inProgress} />
        <StatsCard label="검토 중" value={stats.inReview} />
        <StatsCard label="이번주 마감" value={stats.dueThisWeek} />
      </div>

      <div className="mb-4">
        <CaseFilters status={statusFilter} onStatusChange={setStatusFilter} />
      </div>

      <div className="mb-6">
        <QuickActionsPanel />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {(showMyWorkitems || showApprovalQueue) && (
          <div className="space-y-4 lg:col-span-2">
            {showMyWorkitems && (
              <MyWorkitemsPanel cases={filteredCases} isLoading={isLoading} error={error ?? null} />
            )}
            {showApprovalQueue && <ApprovalQueuePanel />}
          </div>
        )}
        <div className="space-y-4">
          <CaseTimeline />
          <CaseDistributionChart cases={filteredCases} />
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold text-white">케이스 요약</h2>
        <CaseTable data={filteredCases.slice(0, 5)} />
      </div>
    </div>
  );
}
