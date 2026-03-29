/**
 * 케이스 API — Core 서비스 연동.
 * GET /api/v1/cases — 목록 (status, search, pagination)
 * GET /api/v1/cases/:id — 상세
 * GET /api/v1/cases/activities — 활동 타임라인 (case_id 필터 가능)
 * GET /api/v1/cases/:id/documents — 문서 목록
 */
import { coreApi } from './clients';

/* ── 공통 타입 ── */

export interface CaseItem {
  id: string;
  title: string;
  status: string;
  priority: string;
  assignee?: string | null;
  createdAt: string;
  updatedAt?: string | null;
  dueDate?: string | null;
}

export interface CaseListResponse {
  items: CaseItem[];
  total: number;
}

export interface CaseDetailItem {
  id: string;
  title: string;
  status: string;
  priority: string;
  assignee?: string | null;
  createdAt: string;
  updatedAt?: string | null;
  dueDate?: string | null;
}

export interface ActivityItem {
  id: string;
  time: string;
  text: string;
}

export interface ActivitiesResponse {
  items: ActivityItem[];
}

/* ── 파라미터 타입 ── */

export interface ListCasesParams {
  status?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

/* ── API 함수 ── */

/** GET /api/v1/cases — 케이스 목록 (검색·상태 필터·페이지네이션) */
export async function listCases(params?: ListCasesParams): Promise<CaseListResponse> {
  const res = await coreApi.get('/api/v1/cases', {
    params: {
      status: params?.status,
      search: params?.search || undefined,
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    },
  });
  return (res as unknown as CaseListResponse) ?? { items: [], total: 0 };
}

/** GET /api/v1/cases/:id — 케이스 상세 */
export async function getCaseDetail(caseId: string): Promise<CaseDetailItem> {
  const res = await coreApi.get(`/api/v1/cases/${caseId}`);
  return res as unknown as CaseDetailItem;
}

/** GET /api/v1/cases/activities — 활동 타임라인 (case_id 필터 가능) */
export async function listCaseActivities(
  params?: { caseId?: string; limit?: number },
): Promise<ActivitiesResponse> {
  const res = await coreApi.get('/api/v1/cases/activities', {
    params: {
      case_id: params?.caseId,
      limit: params?.limit ?? 20,
    },
  });
  return (res as unknown as ActivitiesResponse) ?? { items: [] };
}
