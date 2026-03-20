/**
 * 데이터 품질 API — Core 서비스 연동
 * 백엔드 엔드포인트가 아직 미구현이므로 Mock 데이터를 포함합니다.
 * 실제 API가 준비되면 fetch 호출로 교체합니다.
 */
import { coreApi } from '@/lib/api/clients';
import type {
  DQRule,
  DQIncident,
  DQScore,
  DQTrendPoint,
  DQTestRunResult,
  CreateDQRulePayload,
} from '../types/data-quality';

// ─── Mock 데이터 (백엔드 미구현 시 사용) ─────────────────

const MOCK_RULES: DQRule[] = [
  {
    id: 'dq-1',
    name: 'check_name_not_null',
    tableName: 'customer_360',
    columnName: 'name',
    type: 'not_null',
    expression: 'name IS NOT NULL',
    severity: 'critical',
    enabled: true,
    level: 'column',
    tags: ['customer'],
    lastResult: { passed: false, failedRows: 17, totalRows: 950, checkedAt: '2026-03-19T16:35:00Z' },
  },
  {
    id: 'dq-2',
    name: 'check_total_orders_range',
    tableName: 'customer_360',
    columnName: 'total_orders',
    type: 'range',
    expression: 'total_orders BETWEEN 0 AND 100000',
    severity: 'warning',
    enabled: true,
    level: 'column',
    tags: ['customer', 'orders'],
    lastResult: { passed: false, failedRows: 5, totalRows: 950, checkedAt: '2026-03-19T16:35:00Z' },
  },
  {
    id: 'dq-3',
    name: 'check_customer_id_unique',
    tableName: 'customer_360',
    columnName: 'customer_id',
    type: 'unique',
    expression: 'customer_id UNIQUE',
    severity: 'critical',
    enabled: true,
    level: 'column',
    tags: ['customer'],
    lastResult: { passed: true, failedRows: 0, totalRows: 950, checkedAt: '2026-03-19T16:35:00Z' },
  },
  {
    id: 'dq-4',
    name: 'check_null_customer_id',
    tableName: 'customer_360',
    columnName: 'customer_id',
    type: 'not_null',
    expression: 'customer_id IS NOT NULL',
    severity: 'critical',
    enabled: true,
    level: 'column',
    lastResult: { passed: true, failedRows: 0, totalRows: 950, checkedAt: '2026-03-19T16:35:00Z' },
  },
  {
    id: 'dq-5',
    name: 'check_email_format',
    tableName: 'customer_360',
    columnName: 'email',
    type: 'regex',
    expression: "email ~ '^[A-Za-z0-9._%+-]+@'",
    severity: 'warning',
    enabled: true,
    level: 'column',
    tags: ['customer'],
    lastResult: { passed: true, failedRows: 0, totalRows: 950, checkedAt: '2026-03-19T16:35:00Z' },
  },
];

const MOCK_INCIDENTS: DQIncident[] = [
  {
    id: 'inc-1',
    ruleId: 'dq-1',
    ruleName: 'check_name_not_null',
    tableName: 'customer_360',
    severity: 'critical',
    status: 'open',
    failedRows: 17,
    detectedAt: '2026-03-19T16:35:00Z',
  },
  {
    id: 'inc-2',
    ruleId: 'dq-2',
    ruleName: 'check_total_orders_range',
    tableName: 'customer_360',
    severity: 'warning',
    status: 'open',
    failedRows: 5,
    detectedAt: '2026-03-19T16:35:00Z',
  },
];

const MOCK_SCORE: DQScore = {
  overall: 87,
  completeness: 92,
  accuracy: 85,
  consistency: 88,
  timeliness: 83,
};

const MOCK_TREND: DQTrendPoint[] = Array.from({ length: 14 }, (_, i) => ({
  date: new Date(Date.now() - (13 - i) * 86400000).toISOString().split('T')[0],
  score: 80 + Math.round(Math.random() * 15),
  testsPassed: 3 + Math.round(Math.random() * 2),
  testsFailed: Math.round(Math.random() * 2),
}));

// ─── API 함수 ─────────────────────────────────────────

/** DQ 규칙 목록 조회 */
export async function getDQRules(): Promise<DQRule[]> {
  try {
    const res = await coreApi.get('/api/data-quality/test-cases');
    return (res as unknown as { data: DQRule[] }).data;
  } catch {
    // 백엔드 미구현 — Mock 반환
    return MOCK_RULES;
  }
}

/** DQ 규칙 생성 */
export async function createDQRule(payload: CreateDQRulePayload): Promise<DQRule> {
  try {
    const res = await coreApi.post('/api/data-quality/test-cases', payload);
    return res as unknown as DQRule;
  } catch {
    // Mock: 생성된 규칙 반환
    const newRule: DQRule = {
      id: `dq-${Date.now()}`,
      ...payload,
      enabled: true,
    };
    MOCK_RULES.push(newRule);
    return newRule;
  }
}

/** DQ 테스트 실행 */
export async function runDQTest(ruleId: string): Promise<DQTestRunResult> {
  try {
    const res = await coreApi.post(`/api/data-quality/test-cases/${ruleId}/run`);
    return res as unknown as DQTestRunResult;
  } catch {
    // Mock: 임의 결과 반환
    const passed = Math.random() > 0.3;
    return {
      ruleId,
      status: passed ? 'success' : 'failed',
      failedRows: passed ? 0 : Math.ceil(Math.random() * 20),
      totalRows: 950,
      executionTimeMs: Math.round(Math.random() * 500 + 100),
      checkedAt: new Date().toISOString(),
    };
  }
}

/** DQ 점수 조회 */
export async function getDQScore(): Promise<DQScore> {
  try {
    const res = await coreApi.get('/api/data-quality/stats');
    return (res as unknown as { data: DQScore }).data;
  } catch {
    return MOCK_SCORE;
  }
}

/** 인시던트 목록 조회 */
export async function getDQIncidents(): Promise<DQIncident[]> {
  try {
    const res = await coreApi.get('/api/data-quality/incidents');
    return (res as unknown as { data: DQIncident[] }).data;
  } catch {
    return MOCK_INCIDENTS;
  }
}

/** 인시던트 상태 변경 */
export async function updateIncidentStatus(
  incidentId: string,
  status: DQIncident['status'],
): Promise<DQIncident> {
  try {
    const res = await coreApi.patch(`/api/data-quality/incidents/${incidentId}`, { status });
    return res as unknown as DQIncident;
  } catch {
    // Mock: 상태 업데이트
    const incident = MOCK_INCIDENTS.find((i) => i.id === incidentId);
    if (incident) incident.status = status;
    return incident ?? MOCK_INCIDENTS[0];
  }
}

/** DQ 추이 데이터 조회 */
export async function getDQTrend(days = 14): Promise<DQTrendPoint[]> {
  try {
    const res = await coreApi.get('/api/data-quality/trend', { params: { days } });
    return (res as unknown as { data: DQTrendPoint[] }).data;
  } catch {
    return MOCK_TREND.slice(-days);
  }
}
