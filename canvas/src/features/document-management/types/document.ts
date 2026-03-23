/**
 * 문서 관리 + HITL 워크플로 타입 정의.
 * Phase 1 Sprint 1a — mock→real 전환의 기반.
 */

/** 문서 상태 FSM: draft → in_review → approved | rejected | changes_requested */
export type DocumentStatus =
  | 'draft'
  | 'in_review'
  | 'approved'
  | 'rejected'
  | 'changes_requested';

/** HITL 상태 전이 규칙 — 허용되지 않는 전이는 UI에서 차단 */
export const VALID_TRANSITIONS: Record<DocumentStatus, DocumentStatus[]> = {
  draft: ['in_review'],
  in_review: ['approved', 'rejected', 'changes_requested'],
  approved: [],                      // 최종 상태
  rejected: ['draft'],               // 반려 후 초안으로 되돌리기 가능
  changes_requested: ['in_review'],  // 수정 후 재검토 요청
};

/** 상태 전이가 유효한지 검증 */
export function canTransition(from: DocumentStatus, to: DocumentStatus): boolean {
  return VALID_TRANSITIONS[from]?.includes(to) ?? false;
}

/** 리뷰 액션 타입 */
export type ReviewAction = 'approve' | 'reject' | 'request_changes' | 'submit_for_review' | 'resubmit';

/** 리뷰 액션 → 대상 상태 매핑 */
export const ACTION_TO_STATUS: Record<ReviewAction, DocumentStatus> = {
  submit_for_review: 'in_review',
  approve: 'approved',
  reject: 'rejected',
  request_changes: 'changes_requested',
  resubmit: 'in_review',
};

/** 문서 모델 */
export interface Document {
  id: string;
  caseId: string;
  name: string;
  type: string;
  status: DocumentStatus;
  version: string;
  content: string;
  isAiGenerated: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

/** 문서 목록 응답 */
export interface DocumentListResponse {
  items: Document[];
  total: number;
}

/** 리뷰 코멘트 */
export interface ReviewComment {
  id: string;
  documentId: string;
  author: string;
  content: string;
  lineStart?: number;
  lineEnd?: number;
  resolved: boolean;
  createdAt: string;
}

/** 문서 Diff 결과 */
export interface DiffResult {
  originalContent: string;
  currentContent: string;
  changeCount: number;
}
