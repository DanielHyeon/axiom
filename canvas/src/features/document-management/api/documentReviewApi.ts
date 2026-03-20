import { coreApi } from '@/lib/api/clients';

export type DocumentReviewAction = 'approve' | 'reject' | 'request_changes';

export interface DocumentReviewRequest {
  action: DocumentReviewAction;
  comment?: string;
}

export interface DocumentReviewResponse {
  documentId: string;
  status: 'approved' | 'rejected' | 'changes_requested';
  message?: string;
}

/**
 * 문서 리뷰 액션 전송.
 * Core POST /api/v1/cases/:caseId/documents/:docId/review (Phase D 계약).
 * 404/5xx 시 호출부(useDocumentReview)에서 롤백 처리.
 */
export async function submitDocumentReview(
  caseId: string,
  docId: string,
  payload: DocumentReviewRequest
): Promise<DocumentReviewResponse> {
  const res = await coreApi.post(
    `/api/v1/cases/${caseId}/documents/${docId}/review`,
    payload
  );
  return res as unknown as DocumentReviewResponse;
}
