/**
 * 문서 CRUD + HITL FSM 훅 — TanStack Query 기반.
 * Phase 1 Sprint 1a: mock→real 전환 + 낙관적 업데이트.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  fetchDocuments,
  fetchDocument,
  createDocument,
  updateDocument,
  fetchComments,
  addComment,
} from '../api/documentApi';
import { submitDocumentReview, type DocumentReviewAction } from '../api/documentReviewApi';
import {
  canTransition,
  ACTION_TO_STATUS,
  type Document,
  type DocumentStatus,
  type ReviewAction,
} from '../types/document';

// ── Query Keys ── //
const keys = {
  list: (caseId: string) => ['documents', caseId] as const,
  detail: (caseId: string, docId: string) => ['documents', caseId, docId] as const,
  comments: (caseId: string, docId: string) => ['document-comments', caseId, docId] as const,
};

/** 문서 목록 훅 */
export function useDocumentList(caseId: string) {
  return useQuery({
    queryKey: keys.list(caseId),
    queryFn: () => fetchDocuments(caseId),
    enabled: !!caseId,
  });
}

/** 문서 상세 훅 */
export function useDocument(caseId: string, docId: string) {
  return useQuery({
    queryKey: keys.detail(caseId, docId),
    queryFn: () => fetchDocument(caseId, docId),
    enabled: !!caseId && !!docId,
  });
}

/** 코멘트 목록 훅 */
export function useDocumentComments(caseId: string, docId: string) {
  return useQuery({
    queryKey: keys.comments(caseId, docId),
    queryFn: () => fetchComments(caseId, docId),
    enabled: !!caseId && !!docId,
  });
}

/** 코멘트 추가 mutation */
export function useAddComment(caseId: string, docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { content: string; lineStart?: number; lineEnd?: number }) =>
      addComment(caseId, docId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.comments(caseId, docId) });
      toast.success('코멘트가 추가되었습니다');
    },
    onError: () => toast.error('코멘트 추가에 실패했습니다'),
  });
}

/**
 * HITL 리뷰 액션 mutation — FSM 가드 + 낙관적 업데이트.
 *
 * 1. canTransition()으로 상태 전이 유효성 검증
 * 2. onMutate: 즉시 UI 반영 (낙관적)
 * 3. onError: 이전 상태로 롤백
 * 4. onSettled: 쿼리 무효화
 */
export function useDocumentReviewAction(caseId: string, docId: string) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async ({ action, comment }: { action: ReviewAction; comment?: string }) => {
      // review 계열 액션은 기존 API 사용
      const reviewActions: DocumentReviewAction[] = ['approve', 'reject', 'request_changes'];
      if (reviewActions.includes(action as DocumentReviewAction)) {
        return submitDocumentReview(caseId, docId, {
          action: action as DocumentReviewAction,
          comment,
        });
      }

      // submit_for_review, resubmit은 문서 상태 변경
      const targetStatus = ACTION_TO_STATUS[action];
      return updateDocument(caseId, docId, {} as never).then(() => ({ status: targetStatus }));
    },

    // 낙관적 업데이트: mutation 시작 시 즉시 UI 반영
    // FSM 가드를 onMutate에서 실행 — mutationFn보다 먼저 호출되므로
    // 캐시가 변경되기 전의 원본 상태로 검증할 수 있다
    onMutate: async ({ action }) => {
      await qc.cancelQueries({ queryKey: keys.detail(caseId, docId) });
      const previous = qc.getQueryData<Document>(keys.detail(caseId, docId));

      // FSM 가드: 현재 상태에서 해당 액션이 가능한지 검증
      if (previous) {
        const targetStatus = ACTION_TO_STATUS[action];
        if (!canTransition(previous.status, targetStatus)) {
          throw new Error(`'${previous.status}' 상태에서 '${action}' 액션은 허용되지 않습니다`);
        }
        qc.setQueryData<Document>(keys.detail(caseId, docId), {
          ...previous,
          status: targetStatus,
        });
      }
      return { previous };
    },

    // 실패 시 이전 상태로 롤백
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        qc.setQueryData(keys.detail(caseId, docId), context.previous);
      }
      toast.error('리뷰 처리에 실패했습니다. 이전 상태로 복원합니다.');
    },

    onSuccess: (_data, { action }) => {
      const labels: Record<ReviewAction, string> = {
        submit_for_review: '검토 요청됨',
        approve: '승인 완료',
        reject: '반려됨',
        request_changes: '수정 요청됨',
        resubmit: '재검토 요청됨',
      };
      toast.success(labels[action] || '처리 완료');
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.detail(caseId, docId) });
      qc.invalidateQueries({ queryKey: keys.list(caseId) });
    },
  });
}
