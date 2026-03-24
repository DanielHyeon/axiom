import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { CaseFilters, type CaseStatusFilter } from '@/features/case-dashboard/components/CaseFilters';
import { CaseTable } from '@/features/case-dashboard/components/CaseTable';

export const CaseListPage: React.FC = () => {
 const { t } = useTranslation();
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
 <h1 className="mb-6 text-2xl font-semibold text-sky-300">{t('cases.title')}</h1>

 <div className="mb-4">
 <CaseFilters status={statusFilter} onStatusChange={setStatusFilter} />
 </div>

 {error && (
 <div className="mb-4 rounded border border-red-900/50 bg-red-900/20 p-4 text-sm text-red-200">
 {t('cases.errorLoadData')}
 </div>
 )}

 {isLoading ? (
 <div className="space-y-3 animate-pulse">
 <div className="h-10 bg-muted rounded w-full" />
 <div className="h-64 bg-muted rounded w-full" />
 </div>
 ) : (
 <CaseTable data={filtered} onRowClick={handleRowClick} />
 )}
 </div>
 );
};
