import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { CaseFilters, type CaseStatusFilter } from '@/features/case-dashboard/components/CaseFilters';
import { CaseTable } from '@/features/case-dashboard/components/CaseTable';

export const CaseListPage: React.FC = () => {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<CaseStatusFilter>('ALL');
  const { data: cases, isLoading, error } = useCases();

  const filtered = useMemo(() => {
    if (!cases) return [];
    if (statusFilter === 'ALL') return cases;
    return cases.filter((c) => c.status === statusFilter);
  }, [cases, statusFilter]);

  const handleRowClick = (c: { id: string }) => {
    navigate(ROUTES.CASES.DETAIL(c.id));
  };

  return (
    <div className="p-6">
      <h1 className="mb-4 text-2xl font-bold text-white">케이스 목록</h1>

      <div className="mb-4">
        <CaseFilters status={statusFilter} onStatusChange={setStatusFilter} />
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-900/50 bg-red-900/20 p-4 text-sm text-red-200">
          데이터를 불러오는 중 오류가 발생했습니다.
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          <div className="h-10 bg-neutral-800 rounded w-full" />
          <div className="h-64 bg-neutral-800 rounded w-full" />
        </div>
      ) : (
        <CaseTable data={filtered} onRowClick={handleRowClick} />
      )}
    </div>
  );
};
