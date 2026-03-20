/**
 * Mock 데이터 생성 모듈 — 인과 분석 + 모델 학습 mock
 *
 * 백엔드가 아직 미구현일 때 사용하는 테스트용 가짜 데이터를 생성한다.
 * 시뮬레이션 관련 mock은 mockSimulation.ts에서 제공.
 */
import type {
  CausalEdge,
  ModelSpec,
  TrainedModel,
} from '../types/wizard';

// 시뮬레이션 관련 mock은 별도 모듈에서 re-export
export {
  generateMockSnapshot,
  generateMockSimulationResult,
} from './mockSimulation';

// ── 인과 관계 mock 데이터 ──

/** 인과 분석 결과 mock: 5개의 가상 엣지를 반환 */
export function generateMockEdges(): {
  edges: CausalEdge[];
  dataRows: number;
  variablesCount: number;
} {
  return {
    edges: [
      {
        source: 'node_costs',
        sourceName: '원가 데이터',
        sourceField: 'cost_index',
        target: 'node_quality',
        targetName: '품질 지표',
        targetField: 'defect_rate',
        method: 'granger',
        strength: 0.85,
        lag: 2,
        pValue: 0.012,
        pearson: -0.72,
        direction: 'negative',
        selected: true,
      },
      {
        source: 'node_production',
        sourceName: '생산 데이터',
        sourceField: 'throughput',
        target: 'node_quality',
        targetName: '품질 지표',
        targetField: 'defect_rate',
        method: 'correlation',
        strength: 0.67,
        lag: 1,
        pValue: 0.034,
        pearson: 0.58,
        direction: 'positive',
        selected: true,
      },
      {
        source: 'node_costs',
        sourceName: '원가 데이터',
        sourceField: 'material_cost',
        target: 'node_production',
        targetName: '생산 데이터',
        targetField: 'throughput',
        method: 'granger',
        strength: 0.73,
        lag: 3,
        pValue: 0.008,
        pearson: -0.65,
        direction: 'negative',
        selected: true,
      },
      {
        source: 'node_quality',
        sourceName: '품질 지표',
        sourceField: 'defect_rate',
        target: 'node_kpi',
        targetName: 'OEE KPI',
        targetField: 'oee_score',
        method: 'granger',
        strength: 0.91,
        lag: 1,
        pValue: 0.002,
        pearson: -0.88,
        direction: 'negative',
        selected: true,
      },
      {
        source: 'node_production',
        sourceName: '생산 데이터',
        sourceField: 'cycle_time',
        target: 'node_kpi',
        targetName: 'OEE KPI',
        targetField: 'oee_score',
        method: 'correlation',
        strength: 0.55,
        lag: 0,
        pValue: 0.078,
        pearson: -0.48,
        direction: 'negative',
        selected: false,
      },
    ],
    dataRows: 1250,
    variablesCount: 12,
  };
}

// ── 모델 스펙 mock 데이터 ──

/** 선택된 엣지를 기반으로 mock 모델 스펙을 자동 생성 */
export function generateMockModelSpecs(edges: CausalEdge[]): ModelSpec[] {
  // 타겟 필드별로 그룹핑하여 모델 스펙 생성
  const targetMap = new Map<string, CausalEdge[]>();
  for (const e of edges.filter((e) => e.selected)) {
    const key = `${e.target}::${e.targetField}`;
    if (!targetMap.has(key)) targetMap.set(key, []);
    targetMap.get(key)!.push(e);
  }

  let order = 0;
  const specs: ModelSpec[] = [];
  for (const [key, groupEdges] of targetMap) {
    const [targetNodeId, targetField] = key.split('::');
    specs.push({
      modelId: `model_${targetField}`,
      name: `${targetField} 예측 모델`,
      targetNodeId,
      targetField,
      executionOrder: order++,
      features: groupEdges.map((e) => ({
        nodeId: e.source,
        field: e.sourceField,
        lag: e.lag,
        score: e.strength,
      })),
    });
  }
  return specs;
}

// ── 학습된 모델 mock 데이터 ──

/** 모델 스펙을 기반으로 mock 학습 결과 생성 (모두 성공) */
export function generateMockTrainedModels(specs: ModelSpec[]): TrainedModel[] {
  return specs.map((s) => ({
    modelId: s.modelId,
    name: s.name,
    inputNodes: s.features.map((f) => `${f.nodeId}::${f.field}`),
    outputNode: `${s.targetNodeId}::${s.targetField}`,
    modelType: 'linear_regression',
    r2Score: 0.7 + Math.random() * 0.25,
    rmse: 0.5 + Math.random() * 2,
    status: 'trained' as const,
    executionOrder: s.executionOrder,
    neo4jSaved: true,
  }));
}
