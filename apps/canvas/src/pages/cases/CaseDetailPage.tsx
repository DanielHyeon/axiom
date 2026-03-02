import React from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { useCaseParams } from '@/lib/routes/params';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { Badge } from '@/components/ui/badge';

const statusLabel: Record<string, string> = {
 PENDING: '대기',
 IN_PROGRESS: '진행 중',
 COMPLETED: '완료',
 REJECTED: '반려',
};

/** 케이스 상세 페이지 (설계 정렬). Phase 1에서 본 구현. */
export const CaseDetailPage: React.FC = () => {
 const { caseId } = useCaseParams();
 const { data: cases, isLoading, error } = useCases();
 const caseItem = cases?.find((c) => c.id === caseId);

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
 <h1 className="text-xl font-semibold text-white">케이스 상세</h1>
 <p className="text-sm text-foreground0">
 케이스를 찾을 수 없습니다. (ID: {caseId})
 </p>
 <Link to={ROUTES.CASES.LIST} className="text-primary hover:underline">
 목록으로
 </Link>
 </div>
 );
 }

 return (
 <div className="space-y-4 p-6">
 <h1 className="text-xl font-semibold text-white">{caseItem.title}</h1>
 <div className="flex flex-wrap items-center gap-2 text-sm">
 <Badge variant="outline">{statusLabel[caseItem.status] ?? caseItem.status}</Badge>
 <Badge variant="secondary">{caseItem.priority}</Badge>
 <span className="text-foreground0">
 생성일: {new Date(caseItem.createdAt).toLocaleDateString('ko-KR')}
 </span>
 {caseItem.dueDate && (
 <span className="text-foreground0">
 마감: {new Date(caseItem.dueDate).toLocaleDateString('ko-KR')}
 </span>
 )}
 </div>
 <div className="flex gap-2">
 <Link
 to={ROUTES.CASES.DOCUMENTS(caseId)}
 className="text-primary hover:underline"
 >
 문서
 </Link>
 <Link
 to={ROUTES.DATA.ONTOLOGY_CASE(caseId)}
 className="text-primary hover:underline"
 >
 온톨로지
 </Link>
 <Link
 to={ROUTES.CASES.SCENARIOS(caseId)}
 className="text-primary hover:underline"
 >
 시나리오
 </Link>
 <Link to={ROUTES.CASES.LIST} className="text-primary hover:underline">
 목록
 </Link>
 </div>
 </div>
 );
};
