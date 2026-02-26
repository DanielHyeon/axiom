/**
 * 라우트 경로 상수 (SSOT).
 * 네비게이션·Link는 이 상수를 사용한다.
 */
export const ROUTES = {
  HOME: '/',
  AUTH: {
    LOGIN: '/auth/login',
    CALLBACK: '/auth/callback',
  },
  DASHBOARD: '/dashboard',
  CASES: {
    LIST: '/cases',
    DETAIL: (caseId: string) => `/cases/${caseId}`,
    DOCUMENTS: (caseId: string) => `/cases/${caseId}/documents`,
    DOCUMENT: (caseId: string, docId: string) => `/cases/${caseId}/documents/${docId}`,
    DOCUMENT_REVIEW: (caseId: string, docId: string) =>
      `/cases/${caseId}/documents/${docId}/review`,
    SCENARIOS: (caseId: string) => `/cases/${caseId}/scenarios`,
  },
  ANALYSIS: {
    OLAP: '/analysis/olap',
    NL2SQL: '/analysis/nl2sql',
    INSIGHT: '/analysis/insight',
  },
  DATA: {
    ONTOLOGY: '/data/ontology',
    ONTOLOGY_CASE: (caseId: string) => `/data/ontology?caseId=${encodeURIComponent(caseId)}`,
    DATASOURCES: '/data/datasources',
  },
  PROCESS_DESIGNER: {
    LIST: '/process-designer',
    BOARD: (boardId: string) => `/process-designer/${boardId}`,
  },
  WATCH: '/watch',
  SETTINGS: '/settings',
  SETTINGS_SYSTEM: '/settings/system',
  SETTINGS_LOGS: '/settings/logs',
  SETTINGS_USERS: '/settings/users',
  SETTINGS_CONFIG: '/settings/config',
} as const;
