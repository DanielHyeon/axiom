import { apiClient } from '@/lib/api-client';

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
 * Core 또는 문서 서비스의 POST /api/v1/cases/:caseId/documents/:docId/review 연동.
 * 404/501 시 호출부에서 롤백 처리.
 */
export async function submitDocumentReview(
  caseId: string,
  docId: string,
  payload: DocumentReviewRequest
): Promise<DocumentReviewResponse> {
  const { data } = await apiClient.post<DocumentReviewResponse>(
    `/api/v1/cases/${caseId}/documents/${docId}/review`,
    payload
  );
  return data;
}
