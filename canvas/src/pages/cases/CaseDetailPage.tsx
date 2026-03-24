import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';
import { useCaseParams } from '@/lib/routes/params';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { Badge } from '@/components/ui/badge';

/** 케이스 상세 페이지 (설계 정렬). Phase 1에서 본 구현. */
export const CaseDetailPage: React.FC = () => {
 const { t, i18n } = useTranslation();
 const { caseId } = useCaseParams();
 const { data: cases, isLoading, error } = useCases();
 const caseItem = cases?.find((c) => c.id === caseId);

 // 현재 로케일에 맞는 날짜 포맷
 const dateLocale = i18n.language === 'ko' ? 'ko-KR' : 'en-US';

 if (isLoading) {
 return (
 <div className="space-y-4 p-6">
 <div className="h-8 w-48 animate-pulse rounded bg-muted" />
 <div className="h-4 w-full animate-pulse rounded bg-muted" />
 </div>
 );
 }

 if (error || !caseItem) {
 return (
 <div className="space-y-4 p-6">
 <h1 className="text-xl font-semibold text-primary-foreground">{t('cases.detail.title')}</h1>
 <p className="text-sm text-foreground0">
 {t('cases.detail.notFound', { id: caseId })}
 </p>
 <Link to={ROUTES.CASES.LIST} className="text-primary hover:underline">
 {t('cases.detail.backToList')}
 </Link>
 </div>
 );
 }

 return (
 <div className="space-y-4 p-6">
 <h1 className="text-xl font-semibold text-primary-foreground">{caseItem.title}</h1>
 <div className="flex flex-wrap items-center gap-2 text-sm">
 <Badge variant="outline">{t(`cases.status.${caseItem.status}`, { defaultValue: caseItem.status })}</Badge>
 <Badge variant="secondary">{caseItem.priority}</Badge>
 <span className="text-foreground0">
 {t('cases.detail.createdAt')}: {new Date(caseItem.createdAt).toLocaleDateString(dateLocale)}
 </span>
 {caseItem.dueDate && (
 <span className="text-foreground0">
 {t('cases.detail.dueDate')}: {new Date(caseItem.dueDate).toLocaleDateString(dateLocale)}
 </span>
 )}
 </div>
 <div className="flex gap-2">
 <Link
 to={ROUTES.CASES.DOCUMENTS(caseId)}
 className="text-primary hover:underline"
 >
 {t('cases.detail.documents')}
 </Link>
 <Link
 to={ROUTES.DATA.ONTOLOGY_CASE(caseId)}
 className="text-primary hover:underline"
 >
 {t('cases.detail.ontology')}
 </Link>
 <Link
 to={ROUTES.CASES.SCENARIOS(caseId)}
 className="text-primary hover:underline"
 >
 {t('cases.detail.scenarios')}
 </Link>
 <Link to={ROUTES.CASES.LIST} className="text-primary hover:underline">
 {t('common.list')}
 </Link>
 </div>
 </div>
 );
};
