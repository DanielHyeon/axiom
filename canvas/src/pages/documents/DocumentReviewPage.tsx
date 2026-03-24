import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';
import { useDocumentParams } from '@/lib/routes/params';
import { Button } from '@/components/ui/button';
import { DocumentDiffViewer } from '@/features/document-management/components/DocumentDiffViewer';
import {
 ReviewPanel,
 type ReviewComment,
} from '@/features/document-management/components/ReviewPanel';
import { useDocumentReview } from '@/features/document-management/hooks/useDocumentReview';
import { useAuthStore } from '@/stores/authStore';

const MOCK_ORIGINAL = `1. 계약 당사자
 갑: (주)원청
 을: (주)하도급

2. 공사 기간
 착공일: 2024-01-15
 준공일: 2024-06-30`;

const MOCK_CURRENT = `1. 계약 당사자
 갑: (주)원청
 을: (주)하도급

2. 공사 기간
 착공일: 2024-01-15
 준공일: 2024-07-15`;

/** 문서 리뷰 페이지. Diff 뷰(react-diff-viewer-continued), 코멘트 쓰레드, 승인/반려/수정요청 API 연동·낙관적 업데이트·실패 시 롤백. */
export function DocumentReviewPage() {
 const { t } = useTranslation();
 const { caseId, docId } = useDocumentParams();
 const userEmail = useAuthStore((s) => s.user?.email ?? 'user');
 const [comments, setComments] = useState<ReviewComment[]>([
 {
 id: '1',
 author: t('documentsPage.m4bf28962'),
 text: t('documentsPage.msg0685a78e'),
 createdAt: new Date(Date.now() - 86400000).toISOString(),
 },
 ]);
 const [actionMessage, setActionMessage] = useState<string | null>(null);

 const { mutate, isPending, isError, error } = useDocumentReview({
 caseId,
 docId,
 onSuccess: (action) => {
 if (action === 'approve') setActionMessage(t('documents.review.approved'));
 else if (action === 'reject') setActionMessage(t('documents.review.rejected'));
 else setActionMessage(t('documents.review.changesRequested'));
 },
 onError: () => {
 setActionMessage(t('documents.review.requestFailed'));
 },
 });

 const handleApprove = () => {
 setActionMessage(null);
 mutate({ action: 'approve' });
 };

 const handleReject = () => {
 setActionMessage(null);
 mutate({ action: 'reject', comment: t('documentsPage.m2235b47a') });
 };

 const handleRequestChanges = () => {
 setActionMessage(null);
 mutate({ action: 'request_changes', comment: t('documentsPage.m45df980b') });
 };

 const handleAddComment = (text: string) => {
 setComments((prev) => [
 ...prev,
 {
 id: String(Date.now()),
 author: userEmail,
 text,
 createdAt: new Date().toISOString(),
 },
 ]);
 };

 const errorMessage = useMemo(() => {
 if (!isError || !error) return null;
 const err = error as { response?: { status?: number } };
 if (err.response?.status === 404) return t('documents.review.apiNotFound');
 return t('documents.review.genericError');
 }, [isError, error, t]);

 return (
 <div className="space-y-4 p-4 md:p-6">
 <h1 className="text-lg md:text-xl font-semibold text-primary-foreground">{t('documents.review.title')}</h1>
 <p className="text-sm text-foreground0">
 {t('documents.review.caseDoc', { caseId, docId })}
 </p>

 <DocumentDiffViewer oldValue={MOCK_ORIGINAL} newValue={MOCK_CURRENT} splitView />

 <ReviewPanel comments={comments} onAddComment={handleAddComment} />

 <div className="flex flex-wrap items-center gap-2">
 <Button onClick={handleApprove} disabled={isPending}>
 {t('common.approve')}
 </Button>
 <Button variant="destructive" onClick={handleReject} disabled={isPending}>
 {t('common.reject')}
 </Button>
 <Button variant="outline" onClick={handleRequestChanges} disabled={isPending}>
 {t('documents.review.requestChanges')}
 </Button>
 </div>

 {(actionMessage || errorMessage) && (
 <p className={`text-sm ${errorMessage ? 'text-destructive' : 'text-muted-foreground'}`}>
 {errorMessage ?? actionMessage}
 </p>
 )}

 <Link
 to={ROUTES.CASES.DOCUMENT(caseId, docId)}
 className="text-primary hover:underline"
 >
 {t('documents.review.goToEditor')}
 </Link>
 </div>
 );
}
