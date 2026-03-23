/**
 * 문서 CRUD API — Core 서비스 연동.
 * Phase 1 Sprint 1a: mock→real 전환.
 * 기존 documentReviewApi.ts의 리뷰 액션과 분리하여 CRUD를 담당한다.
 */

import { coreApi } from '@/lib/api/clients';
import type { Document, DocumentListResponse, ReviewComment } from '../types/document';

const BASE = '/api/v1/cases';

/** 문서 목록 조회 */
export async function fetchDocuments(caseId: string): Promise<DocumentListResponse> {
  const res = await coreApi.get(`${BASE}/${caseId}/documents`);
  return res as unknown as DocumentListResponse;
}

/** 문서 상세 조회 */
export async function fetchDocument(caseId: string, docId: string): Promise<Document> {
  const res = await coreApi.get(`${BASE}/${caseId}/documents/${docId}`);
  return res as unknown as Document;
}

/** 문서 생성 */
export async function createDocument(
  caseId: string,
  payload: { name: string; type: string; content: string },
): Promise<Document> {
  const res = await coreApi.post(`${BASE}/${caseId}/documents`, payload);
  return res as unknown as Document;
}

/** 문서 수정 */
export async function updateDocument(
  caseId: string,
  docId: string,
  payload: Partial<Pick<Document, 'name' | 'content'>>,
): Promise<Document> {
  const res = await coreApi.put(`${BASE}/${caseId}/documents/${docId}`, payload);
  return res as unknown as Document;
}

/** 코멘트 목록 조회 */
export async function fetchComments(caseId: string, docId: string): Promise<ReviewComment[]> {
  const res = await coreApi.get(`${BASE}/${caseId}/documents/${docId}/comments`);
  return res as unknown as ReviewComment[];
}

/** 코멘트 추가 */
export async function addComment(
  caseId: string,
  docId: string,
  payload: { content: string; lineStart?: number; lineEnd?: number },
): Promise<ReviewComment> {
  const res = await coreApi.post(`${BASE}/${caseId}/documents/${docId}/comments`, payload);
  return res as unknown as ReviewComment;
}
