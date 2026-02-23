/**
 * 케이스 목록·활동 API (Core GET /api/v1/cases, GET /api/v1/cases/activities).
 * Canvas Full-spec Phase A.
 */
import { coreApi } from './clients';

export interface CaseItem {
  id: string;
  title: string;
  status: string;
  priority: string;
  createdAt: string;
  dueDate?: string | null;
}

export interface CaseListResponse {
  items: CaseItem[];
  total: number;
}

export interface ActivityItem {
  id: string;
  time: string;
  text: string;
}

export interface ActivitiesResponse {
  items: ActivityItem[];
}

export interface ListCasesParams {
  status?: string;
  limit?: number;
  offset?: number;
}

/** GET /api/v1/cases — 케이스 목록 */
export async function listCases(params?: ListCasesParams): Promise<CaseListResponse> {
  const data = await coreApi.get<CaseListResponse>('/api/v1/cases', {
    params: {
      status: params?.status,
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    },
  });
  return (data as CaseListResponse) ?? { items: [], total: 0 };
}

/** GET /api/v1/cases/activities — 최근 활동 */
export async function listCaseActivities(limit?: number): Promise<ActivitiesResponse> {
  const data = await coreApi.get<ActivitiesResponse>('/api/v1/cases/activities', {
    params: { limit: limit ?? 20 },
  });
  return (data as ActivitiesResponse) ?? { items: [] };
}
