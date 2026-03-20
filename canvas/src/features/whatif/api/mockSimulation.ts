/**
 * 시뮬레이션 Mock 데이터 모듈
 *
 * DAG 시뮬레이션 실행 결과와 베이스라인 스냅샷의 mock 데이터를 생성한다.
 * 백엔드가 아직 미구현일 때 simulationApi.ts에서 폴백으로 사용.
 */
import type { SimulationResult, SnapshotData } from '../types/wizard';

/** 베이스라인 스냅샷 mock 데이터 생성 */
export function generateMockSnapshot(): SnapshotData {
  return {
    date: new Date().toISOString().split('T')[0],
    snapshot: {
      'node_costs::cost_index': 100,
      'node_costs::material_cost': 45.5,
      'node_production::throughput': 850,
      'node_production::cycle_time': 12.3,
      'node_quality::defect_rate': 3.2,
      'node_kpi::oee_score': 78.5,
    },
    snapshotByNode: {
      node_costs: {
        nodeName: '원가 데이터',
        fields: { cost_index: 100, material_cost: 45.5 },
      },
      node_production: {
        nodeName: '생산 데이터',
        fields: { throughput: 850, cycle_time: 12.3 },
      },
      node_quality: {
        nodeName: '품질 지표',
        fields: { defect_rate: 3.2 },
      },
      node_kpi: {
        nodeName: 'OEE KPI',
        fields: { oee_score: 78.5 },
      },
    },
    availableDates: [],
    fieldDescriptions: {
      cost_index: '원가 지수',
      material_cost: '원자재 비용',
      throughput: '생산량',
      cycle_time: '사이클 타임',
      defect_rate: '불량률',
      oee_score: 'OEE 점수',
    },
  };
}

/** DAG 시뮬레이션 결과 mock 데이터 생성 */
export function generateMockSimulationResult(
  scenarioName: string,
  interventions: Array<{ nodeId: string; field: string; value: number; description: string }>
): SimulationResult {
  return {
    scenarioName,
    interventions,
    traces: [
      {
        modelId: 'model_defect_rate',
        modelName: '불량률 예측 모델',
        inputs: { cost_index: interventions[0]?.value ?? 120 },
        outputField: 'node_quality::defect_rate',
        baselineValue: 3.2,
        predictedValue: 4.1,
        delta: 0.9,
        pctChange: 28.1,
        wave: 0,
        effectiveDay: 2,
        triggeredBy: ['node_costs::cost_index'],
      },
      {
        modelId: 'model_oee_score',
        modelName: 'OEE 점수 예측 모델',
        inputs: { defect_rate: 4.1 },
        outputField: 'node_kpi::oee_score',
        baselineValue: 78.5,
        predictedValue: 72.3,
        delta: -6.2,
        pctChange: -7.9,
        wave: 1,
        effectiveDay: 3,
        triggeredBy: ['node_quality::defect_rate'],
      },
    ],
    timeline: {
      '0': [],
      '2': [
        {
          modelId: 'model_defect_rate',
          modelName: '불량률 예측 모델',
          inputs: { cost_index: interventions[0]?.value ?? 120 },
          outputField: 'node_quality::defect_rate',
          baselineValue: 3.2,
          predictedValue: 4.1,
          delta: 0.9,
          pctChange: 28.1,
          wave: 0,
          effectiveDay: 2,
          triggeredBy: ['node_costs::cost_index'],
        },
      ],
      '3': [
        {
          modelId: 'model_oee_score',
          modelName: 'OEE 점수 예측 모델',
          inputs: { defect_rate: 4.1 },
          outputField: 'node_kpi::oee_score',
          baselineValue: 78.5,
          predictedValue: 72.3,
          delta: -6.2,
          pctChange: -7.9,
          wave: 1,
          effectiveDay: 3,
          triggeredBy: ['node_quality::defect_rate'],
        },
      ],
    },
    finalState: {
      'node_costs::cost_index': interventions[0]?.value ?? 120,
      'node_costs::material_cost': 45.5,
      'node_production::throughput': 850,
      'node_quality::defect_rate': 4.1,
      'node_kpi::oee_score': 72.3,
    },
    baselineState: {
      'node_costs::cost_index': 100,
      'node_costs::material_cost': 45.5,
      'node_production::throughput': 850,
      'node_quality::defect_rate': 3.2,
      'node_kpi::oee_score': 78.5,
    },
    deltas: {
      'node_costs::cost_index': (interventions[0]?.value ?? 120) - 100,
      'node_quality::defect_rate': 0.9,
      'node_kpi::oee_score': -6.2,
    },
    propagationWaves: 2,
    executedAt: new Date().toISOString(),
  };
}
