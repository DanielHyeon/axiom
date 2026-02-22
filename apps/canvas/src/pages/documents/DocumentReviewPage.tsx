import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
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
  const { caseId, docId } = useDocumentParams();
  const userEmail = useAuthStore((s) => s.user?.email ?? '사용자');
  const [comments, setComments] = useState<ReviewComment[]>([
    {
      id: '1',
      author: '검토자1',
      text: '준공일 변경분 확인 부탁드립니다.',
      createdAt: new Date(Date.now() - 86400000).toISOString(),
    },
  ]);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const { mutate, isPending, isError, error } = useDocumentReview({
    caseId,
    docId,
    onSuccess: (action) => {
      if (action === 'approve') setActionMessage('승인되었습니다.');
      else if (action === 'reject') setActionMessage('반려 처리되었습니다.');
      else setActionMessage('수정 요청이 전송되었습니다.');
    },
    onError: () => {
      setActionMessage(
        '요청 처리에 실패했습니다. 리뷰 API가 아직 등록되지 않았을 수 있습니다.'
      );
    },
  });

  const handleApprove = () => {
    setActionMessage(null);
    mutate({ action: 'approve' });
  };

  const handleReject = () => {
    setActionMessage(null);
    mutate({ action: 'reject', comment: '내용 검토 후 반려합니다.' });
  };

  const handleRequestChanges = () => {
    setActionMessage(null);
    mutate({ action: 'request_changes', comment: '준공일 등 수정 후 재제출 부탁드립니다.' });
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
    if (err.response?.status === 404) return '리뷰 API가 등록되지 않았습니다.';
    return '요청 처리에 실패했습니다.';
  }, [isError, error]);

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-xl font-semibold text-white">문서 리뷰</h1>
      <p className="text-sm text-neutral-500">
        케이스: {caseId} / 문서: {docId}
      </p>

      <DocumentDiffViewer oldValue={MOCK_ORIGINAL} newValue={MOCK_CURRENT} splitView />

      <ReviewPanel comments={comments} onAddComment={handleAddComment} />

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={handleApprove} disabled={isPending}>
          승인
        </Button>
        <Button variant="destructive" onClick={handleReject} disabled={isPending}>
          반려
        </Button>
        <Button variant="outline" onClick={handleRequestChanges} disabled={isPending}>
          수정 요청
        </Button>
      </div>

      {(actionMessage || errorMessage) && (
        <p className={`text-sm ${errorMessage ? 'text-red-400' : 'text-neutral-400'}`}>
          {errorMessage ?? actionMessage}
        </p>
      )}

      <Link
        to={ROUTES.CASES.DOCUMENT(caseId, docId)}
        className="text-blue-600 hover:underline"
      >
        편집으로
      </Link>
    </div>
  );
}
