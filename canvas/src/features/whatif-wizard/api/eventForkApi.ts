/**
 * Event Fork API 클라이언트
 *
 * Vision 서비스의 Event Fork 시뮬레이션 엔드포인트를 호출한다.
 * 브랜치 생성, 시뮬레이션 실행, 시나리오 비교 등의 기능을 제공한다.
 */
import { visionApi } from '@/lib/api/clients';
import type {
  SimulationBranch,
  ForkResult,
  ForkEvent,
  InterventionSpec,
  ScenarioComparisonResult,
} from '../types/whatifWizard.types';

// ── 베이스 경로 ──
const base = (caseId: string) => `/api/v3/cases/${caseId}/event-fork`;

// ── 요청/응답 타입 (API 원형, snake_case) ──

interface RawBranch {
  branch_id: string;
  name: string;
  description?: string;
  interventions: Array<{
    node_id: string;
    node_name: string;
    field: string;
    value: number;
    baseline_value: number;
    description: string;
  }>;
  status: string;
  created_at: string;
  completed_at?: string;
}

interface RawForkResult {
  branch_id: string;
  scenario_name: string;
  status: string;
  kpi_deltas: Record<string, number>;
  kpi_baselines: Record<string, number>;
  kpi_results: Record<string, number>;
  events: Array<{
    id: string;
    type: string;
    timestamp: string;
    node_id: string;
    description: string;
    data?: Record<string, unknown>;
  }>;
  executed_at: string;
}

interface RawEvent {
  id: string;
  type: string;
  timestamp: string;
  node_id: string;
  description: string;
  data?: Record<string, unknown>;
}

interface RawComparison {
  metrics: string[];
  scenarios: Array<{
    id: string;
    name: string;
    values: Record<string, number>;
    deltas: Record<string, number>;
  }>;
}

// ── 변환 헬퍼 ──

/** 백엔드 snake_case → 프론트엔드 camelCase 변환 */
function toBranch(raw: RawBranch): SimulationBranch {
  return {
    branchId: raw.branch_id,
    name: raw.name,
    description: raw.description,
    interventions: (raw.interventions ?? []).map((iv) => ({
      nodeId: iv.node_id,
      nodeName: iv.node_name,
      field: iv.field,
      value: iv.value,
      baselineValue: iv.baseline_value,
      description: iv.description,
    })),
    status: raw.status as SimulationBranch['status'],
    createdAt: raw.created_at,
    completedAt: raw.completed_at,
  };
}

function toForkResult(raw: RawForkResult): ForkResult {
  return {
    branchId: raw.branch_id,
    scenarioName: raw.scenario_name,
    status: raw.status as ForkResult['status'],
    kpiDeltas: raw.kpi_deltas ?? {},
    kpiBaselines: raw.kpi_baselines ?? {},
    kpiResults: raw.kpi_results ?? {},
    events: (raw.events ?? []).map((e) => ({
      id: e.id,
      type: e.type,
      timestamp: e.timestamp,
      nodeId: e.node_id,
      description: e.description,
      data: e.data,
    })),
    executedAt: raw.executed_at,
  };
}

function toEvent(raw: RawEvent): ForkEvent {
  return {
    id: raw.id,
    type: raw.type,
    timestamp: raw.timestamp,
    nodeId: raw.node_id,
    description: raw.description,
    data: raw.data,
  };
}

// ── API 함수들 ──

/**
 * 브랜치 생성
 *
 * 새로운 Event Fork 시뮬레이션 브랜치를 생성한다.
 * 브랜치에는 이름, 설명, 개입 목록이 포함된다.
 */
export async function createBranch(
  caseId: string,
  params: {
    name: string;
    description?: string;
    interventions: InterventionSpec[];
  },
): Promise<string> {
  const res = (await visionApi.post(base(caseId), {
    name: params.name,
    description: params.description,
    interventions: params.interventions.map((iv) => ({
      node_id: iv.nodeId,
      node_name: iv.nodeName,
      field: iv.field,
      value: iv.value,
      baseline_value: iv.baselineValue,
      description: iv.description,
    })),
  })) as { branch_id: string };

  return res.branch_id;
}

/**
 * 시뮬레이션 실행
 *
 * 지정된 브랜치에서 Event Fork 시뮬레이션을 실행한다.
 * 이벤트 스트림을 복제하고 개입 값을 적용하여 KPI 변화를 계산한다.
 */
export async function runSimulation(
  caseId: string,
  branchId: string,
): Promise<ForkResult> {
  const res = (await visionApi.post(
    `${base(caseId)}/${branchId}/simulate`,
    {},
  )) as RawForkResult;

  return toForkResult(res);
}

/**
 * 브랜치 상세 조회
 */
export async function getBranch(
  caseId: string,
  branchId: string,
): Promise<SimulationBranch> {
  const res = (await visionApi.get(
    `${base(caseId)}/${branchId}`,
  )) as RawBranch;

  return toBranch(res);
}

/**
 * 브랜치 이벤트 목록 조회
 *
 * Event Fork 시뮬레이션에서 생성된 이벤트 타임라인을 조회한다.
 */
export async function getBranchEvents(
  caseId: string,
  branchId: string,
  limit = 50,
  offset = 0,
): Promise<{ events: ForkEvent[]; total: number }> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  const res = (await visionApi.get(
    `${base(caseId)}/${branchId}/events?${params}`,
  )) as { events: RawEvent[]; total: number };

  return {
    events: (res.events ?? []).map(toEvent),
    total: res.total ?? 0,
  };
}

/**
 * 시나리오 비교
 *
 * 여러 브랜치의 시뮬레이션 결과를 비교 매트릭스로 반환한다.
 */
export async function compareScenarios(
  caseId: string,
  branchIds: string[],
): Promise<ScenarioComparisonResult> {
  const ids = branchIds.join(',');
  const res = (await visionApi.get(
    `${base(caseId)}/compare?branch_ids=${ids}`,
  )) as RawComparison;

  return {
    metrics: res.metrics ?? [],
    scenarios: res.scenarios ?? [],
  };
}

/**
 * 브랜치 삭제
 */
export async function deleteBranch(
  caseId: string,
  branchId: string,
): Promise<void> {
  await visionApi.delete(`${base(caseId)}/${branchId}`);
}
