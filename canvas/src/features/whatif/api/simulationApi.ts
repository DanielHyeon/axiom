/**
 * 시뮬레이션(Simulation) API 모듈
 *
 * Vision 서비스에 베이스라인 스냅샷 조회와
 * What-if DAG 시뮬레이션 실행을 요청한다.
 */
import { visionApi } from '@/lib/api/clients';
import type {
  SimulationResult,
  SimulationTrace,
  SnapshotData,
} from '../types/wizard';
import type { SnapshotResponse, SimulateResponse } from './types';
import { dagBase, rawTraceToTrace } from './types';
import { generateMockSnapshot, generateMockSimulationResult } from './mockData';

/**
 * 베이스라인 스냅샷 조회 (Step 5)
 *
 * 특정 날짜의 베이스라인 데이터를 가져와 노드별로 그룹핑한다.
 * "nodeId::field" 형식의 키를 nodeId별 필드 맵으로 변환.
 */
export async function getSnapshot(
  caseId: string,
  date?: string
): Promise<SnapshotData> {
  try {
    const params = date ? { date } : {};
    const res = (await visionApi.get(`${dagBase(caseId)}/snapshot`, {
      params,
    })) as SnapshotResponse;

    // 서버 응답을 SnapshotData 형식으로 변환
    const snapshot = res.data ?? {};
    const snapshotByNode: SnapshotData['snapshotByNode'] = {};

    // "nodeId::field" 형식의 키를 nodeId별로 그룹핑
    for (const [key, value] of Object.entries(snapshot)) {
      const [nodeId, field] = key.includes('::') ? key.split('::') : [key, key];
      if (!snapshotByNode[nodeId]) {
        snapshotByNode[nodeId] = { nodeName: nodeId, fields: {} };
      }
      snapshotByNode[nodeId].fields[field] = value;
    }

    return {
      date: res.snapshot_date ?? new Date().toISOString().split('T')[0],
      snapshot,
      snapshotByNode,
      availableDates: [],
      fieldDescriptions: {},
    };
  } catch {
    return generateMockSnapshot();
  }
}

/**
 * DAG 시뮬레이션 실행 (Step 5)
 *
 * 개입(intervention) 값을 설정하고 DAG를 통해 전파 시뮬레이션을 실행한다.
 * 결과에는 전파 경로(traces), 타임라인, 최종 상태 등이 포함된다.
 */
export async function runSimulation(
  caseId: string,
  scenarioName: string,
  interventions: Array<{ nodeId: string; field: string; value: number; description: string }>,
  baselineData?: Record<string, number>
): Promise<SimulationResult> {
  try {
    const res = (await visionApi.post(`${dagBase(caseId)}/simulate`, {
      scenario_name: scenarioName,
      interventions: interventions.map((iv) => ({
        nodeId: iv.nodeId,
        field: iv.field,
        value: iv.value,
        description: iv.description,
      })),
      baseline_data: baselineData,
    })) as SimulateResponse;

    // 타임라인 변환: 일자별 RawTrace → SimulationTrace
    const timeline: Record<string, SimulationTrace[]> = {};
    for (const [day, traces] of Object.entries(res.timeline ?? {})) {
      timeline[day] = (traces ?? []).map(rawTraceToTrace);
    }

    return {
      scenarioName: res.scenario_name,
      interventions: (res.interventions ?? []).map((iv) => ({
        nodeId: iv.node_id,
        field: iv.field,
        value: iv.value,
        description: iv.description,
      })),
      traces: (res.traces ?? []).map(rawTraceToTrace),
      timeline,
      finalState: res.final_state ?? {},
      baselineState: res.baseline_state ?? {},
      deltas: res.deltas ?? {},
      propagationWaves: res.propagation_waves ?? 0,
      executedAt: res.executed_at ?? new Date().toISOString(),
    };
  } catch {
    return generateMockSimulationResult(scenarioName, interventions);
  }
}
