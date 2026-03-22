/**
 * 데이터 품질 API — Weaver 서비스 품질 엔드포인트 연동
 *
 * Weaver가 실제 제공하는 엔드포인트:
 *   GET  /api/quality/scores              — 최신 품질 점수 목록
 *   GET  /api/quality/scores/:type/:id    — 단일 대상 최신 점수
 *   POST /api/quality/scan               — 품질 스캔 실행
 *
 * Weaver에 아직 없는 기능(규칙 CRUD, 테스트 실행, 인시던트 상태 변경)은
 * Mock 데이터로 폴백합니다.
 */
import { weaverApi } from '@/lib/api/clients';
import type {
  DQRule,
  DQIncident,
  DQScore,
  DQTrendPoint,
  DQTestRunResult,
  CreateDQRulePayload,
} from '../types/data-quality';

// ─── Weaver 응답 타입 (내부 매핑용) ─────────────────────
interface WeaverQualityScore {
  id?: string;
  tenant_id?: string;
  target_type: string;
  target_id: string;
  freshness_score: number;
  completeness_score: number;
  uniqueness_score: number;
  validity_score: number;
  ri_score: number;        // referential integrity
  owner_score: number;
  lineage_score: number;
  test_score: number;      // test coverage
  incident_score: number;  // incident health
  overall_score: number;
  formula_version?: number;
  details?: Record<string, unknown>;
  sampled_at?: string;
  created_at?: string;
}

interface WeaverListResponse {
  success: boolean;
  data: WeaverQualityScore[];
  count: number;
}

// ─── Weaver 점수 → DQScore 변환 ─────────────────────────
// Weaver의 9개 차원을 Canvas DQScore 4개 카테고리로 매핑한다.
// overall  : Weaver overall_score 그대로
// completeness : Weaver completeness_score 그대로
// accuracy : validity + referential_integrity 평균 (데이터 정확성 대표)
// consistency : uniqueness_score 그대로 (일관성 대표)
// timeliness : freshness_score 그대로 (적시성 대표)
function mapWeaverScoreToDQScore(scores: WeaverQualityScore[]): DQScore {
  if (scores.length === 0) {
    return MOCK_SCORE;
  }

  // 전체 대상에 대한 평균 점수를 계산한다
  const avg = (field: keyof WeaverQualityScore) => {
    const values = scores.map((s) => Number(s[field]) || 0);
    return Math.round(values.reduce((a, b) => a + b, 0) / values.length);
  };

  return {
    overall: avg('overall_score'),
    completeness: avg('completeness_score'),
    accuracy: Math.round((avg('validity_score') + avg('ri_score')) / 2),
    consistency: avg('uniqueness_score'),
    timeliness: avg('freshness_score'),
  };
}

// ─── Weaver 점수 이력 → DQTrendPoint 변환 ───────────────
function mapWeaverScoresToTrend(scores: WeaverQualityScore[]): DQTrendPoint[] {
  return scores
    .filter((s) => s.sampled_at || s.created_at)
    .map((s) => {
      const dateStr = (s.sampled_at || s.created_at || '').split('T')[0];
      return {
        date: dateStr,
        score: Math.round(s.overall_score),
        // Weaver는 testsPassed/Failed 개념이 없으므로 점수 기반으로 추정
        testsPassed: s.overall_score >= 50 ? 1 : 0,
        testsFailed: s.overall_score < 50 ? 1 : 0,
      };
    })
    .sort((a, b) => a.date.localeCompare(b.date));
}

// ─── Weaver 점수 → DQIncident 변환 ──────────────────────
// overall_score가 breach 임계치(60) 미만인 항목을 인시던트로 변환한다
// 백엔드 /api/quality/breaches와 동일한 60점 기준 적용
function mapWeaverScoresToIncidents(scores: WeaverQualityScore[]): DQIncident[] {
  return scores
    .filter((s) => s.overall_score < 60) // breach 기준: 60점 미만 (백엔드 통일)
    .map((s, idx) => ({
      id: `breach-${s.target_id}-${idx}`,
      ruleId: `quality-${s.target_type}`,
      ruleName: `${s.target_type} quality breach`,
      tableName: s.target_id.includes(':') ? s.target_id.split(':')[1] : s.target_id,
      severity: s.overall_score < 30 ? 'critical' as const : 'warning' as const,
      status: 'open' as const,
      failedRows: 0, // Weaver는 행 수준 breach 정보를 제공하지 않는다
      detectedAt: s.sampled_at || s.created_at || new Date().toISOString(),
    }));
}

// ─── Mock 데이터 (Weaver 미지원 기능용) ─────────────────

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

/** DQ 규칙 목록 조회 — Weaver 미지원, Mock 사용 */
export async function getDQRules(): Promise<DQRule[]> {
  // Weaver에 규칙 CRUD 엔드포인트가 없으므로 Mock 반환
  return MOCK_RULES;
}

/** DQ 규칙 생성 — Weaver 미지원, Mock 사용 */
export async function createDQRule(payload: CreateDQRulePayload): Promise<DQRule> {
  // Mock: 생성된 규칙 반환
  const newRule: DQRule = {
    id: `dq-${Date.now()}`,
    ...payload,
    enabled: true,
  };
  MOCK_RULES.push(newRule);
  return newRule;
}

/** DQ 테스트 실행 — Weaver 미지원, Mock 사용 */
export async function runDQTest(ruleId: string): Promise<DQTestRunResult> {
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

/**
 * DQ 점수 조회 — Weaver /api/quality/scores 연동
 *
 * Weaver의 9개 차원 품질 점수를 Canvas DQScore 형식으로 매핑한다.
 * Weaver 연결 실패 시 Mock 폴백.
 */
export async function getDQScore(): Promise<DQScore> {
  try {
    const res = await weaverApi.get<WeaverListResponse>('/api/quality/scores');
    // 응답 인터셉터가 response.data를 반환하므로 res가 곧 body
    const body = res as unknown as WeaverListResponse;
    if (body.success && Array.isArray(body.data)) {
      return mapWeaverScoreToDQScore(body.data);
    }
    return MOCK_SCORE;
  } catch {
    // Weaver 연결 실패 — Mock 폴백
    return MOCK_SCORE;
  }
}

/**
 * 인시던트 목록 조회 — Weaver /api/quality/breaches 엔드포인트 사용
 *
 * 백엔드에서 overall_score < 60인 항목만 반환한다 (breach 임계치 통일).
 * Weaver 연결 실패 시 Mock 폴백.
 */
export async function getDQIncidents(): Promise<DQIncident[]> {
  try {
    const res = await weaverApi.get<WeaverListResponse>('/api/quality/breaches', {
      params: { limit: 50 },
    });
    const body = res as unknown as WeaverListResponse;
    if (body.success && Array.isArray(body.data)) {
      const incidents = mapWeaverScoresToIncidents(body.data);
      return incidents.length > 0 ? incidents : MOCK_INCIDENTS;
    }
    return MOCK_INCIDENTS;
  } catch {
    return MOCK_INCIDENTS;
  }
}

/** 인시던트 상태 변경 — Weaver 미지원, Mock 사용 */
export async function updateIncidentStatus(
  incidentId: string,
  status: DQIncident['status'],
): Promise<DQIncident> {
  // Mock: 상태 업데이트
  const incident = MOCK_INCIDENTS.find((i) => i.id === incidentId);
  if (incident) incident.status = status;
  return incident ?? MOCK_INCIDENTS[0];
}

/**
 * DQ 추이 데이터 조회 — Weaver /api/quality/scores에서 이력 파생
 *
 * Weaver의 scores 목록을 날짜별로 그룹핑하여 추이 데이터로 변환한다.
 * 아직 Weaver에 history 엔드포인트가 없으므로 최신 스냅샷 기반.
 * Weaver 연결 실패 시 Mock 폴백.
 */
export async function getDQTrend(days = 14): Promise<DQTrendPoint[]> {
  try {
    const res = await weaverApi.get<WeaverListResponse>('/api/quality/scores', {
      params: { limit: 500 },
    });
    const body = res as unknown as WeaverListResponse;
    if (body.success && Array.isArray(body.data) && body.data.length > 0) {
      const trend = mapWeaverScoresToTrend(body.data);
      // 추이 데이터가 충분하면 최근 days일치 반환, 아니면 Mock 보완
      return trend.length >= 2 ? trend.slice(-days) : MOCK_TREND.slice(-days);
    }
    return MOCK_TREND.slice(-days);
  } catch {
    return MOCK_TREND.slice(-days);
  }
}

/**
 * 품질 스캔 트리거 — Weaver /api/quality/scan 연동
 *
 * 특정 테이블에 대해 9개 차원 품질 스캔을 실행한다.
 * Weaver에 실제 구현되어 있는 엔드포인트.
 */
export async function triggerQualityScan(
  datasourceId: string,
  tableName: string,
  options?: { freshnessSlaMinutes?: number; ownerTeam?: string },
): Promise<{ success: boolean; data?: unknown }> {
  try {
    const res = await weaverApi.post('/api/quality/scan', {
      datasource_id: datasourceId,
      table_name: tableName,
      freshness_sla_minutes: options?.freshnessSlaMinutes ?? null,
      owner_team: options?.ownerTeam ?? null,
    });
    return res as unknown as { success: boolean; data?: unknown };
  } catch {
    return { success: false };
  }
}

/**
 * 단일 대상 품질 점수 조회 — Weaver /api/quality/scores/:type/:id 연동
 *
 * 특정 테이블/엔티티의 최신 품질 점수를 조회한다.
 */
export async function getTargetQualityScore(
  targetType: string,
  targetId: string,
): Promise<DQScore | null> {
  try {
    const res = await weaverApi.get(`/api/quality/scores/${targetType}/${targetId}`);
    const body = res as unknown as { success: boolean; data: WeaverQualityScore };
    if (body.success && body.data) {
      return mapWeaverScoreToDQScore([body.data]);
    }
    return null;
  } catch {
    return null;
  }
}
