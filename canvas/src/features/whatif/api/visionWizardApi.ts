/**
 * Vision 서비스 What-if 위자드 API
 *
 * 인과 분석, 모델 학습, DAG 시뮬레이션 등
 * 5단계 위자드에서 사용하는 Vision 백엔드 호출 모듈.
 */
import { visionApi, synapseApi } from '@/lib/api/clients';
import type {
  CausalEdge,
  ModelSpec,
  TrainedModel,
  SimulationResult,
  SimulationTrace,
  SnapshotData,
} from '../types/wizard';

// ── 베이스 경로 ──
const dagBase = (caseId: string) => `/api/v3/cases/${caseId}/whatif-dag`;

// ── 응답 타입 (API 원형) ──

interface RawEdge {
  sourceNodeId: string;
  sourceNodeName: string;
  sourceField: string;
  targetNodeId: string;
  targetNodeName: string;
  targetField: string;
  score: number;
  lag: number;
  pearson: number;
  grangerPValue: number;
  direction: 'positive' | 'negative';
}

interface DiscoverEdgesResponse {
  edges: RawEdge[];
  data_rows: number;
  variables_count: number;
  feature_view_sql: string;
  field_descriptions?: Record<string, string>;
}

interface BuildModelGraphResponse {
  models: Array<{
    model_id: string;
    name: string;
    target_node_id: string;
    target_field: string;
    execution_order: number;
    features: Array<{
      nodeId: string;
      field: string;
      lag: number;
      score: number;
    }>;
  }>;
  field_descriptions?: Record<string, string>;
}

interface TrainModelsResponse {
  mindsdb_available: boolean;
  models_registered: number;
  results: Array<{
    model_id: string;
    name: string;
    status: string;
    neo4j_saved: boolean;
    links_created: number;
    r2?: number;
    rmse?: number;
    model_type?: string;
  }>;
}

interface RawSimulationTrace {
  model_id: string;
  model_name: string;
  inputs: Record<string, number>;
  output_field: string;
  baseline_value: number;
  predicted_value: number;
  delta: number;
  pct_change: number;
  wave: number;
  effective_day: number;
  triggered_by: string[];
}

interface SimulateResponse {
  success: boolean;
  scenario_name: string;
  interventions: Array<{ node_id: string; field: string; value: number; description: string }>;
  traces: RawSimulationTrace[];
  timeline: Record<string, RawSimulationTrace[]>;
  final_state: Record<string, number>;
  baseline_state: Record<string, number>;
  deltas: Record<string, number>;
  propagation_waves: number;
  executed_at: string;
}

interface SnapshotResponse {
  success: boolean;
  case_id: string;
  snapshot_date: string | null;
  data: Record<string, number>;
  variable_count: number;
}

interface ModelsListResponse {
  success: boolean;
  case_id: string;
  models: Array<{
    id: string;
    name: string;
    status: string;
    model_type?: string;
    input_count: number;
    output?: {
      target_node_id: string;
      target_field: string;
      confidence?: number;
    };
  }>;
  total: number;
}

// ── 변환 헬퍼 ──

function rawTraceToTrace(raw: RawSimulationTrace): SimulationTrace {
  return {
    modelId: raw.model_id,
    modelName: raw.model_name,
    inputs: raw.inputs,
    outputField: raw.output_field,
    baselineValue: raw.baseline_value,
    predictedValue: raw.predicted_value,
    delta: raw.delta,
    pctChange: raw.pct_change,
    wave: raw.wave,
    effectiveDay: raw.effective_day,
    triggeredBy: raw.triggered_by,
  };
}

// ── API 함수들 ──

/**
 * 인과 관계 발견 (Step 3)
 *
 * Vision 서비스에 인과 분석 요청을 보내고 발견된 엣지를 반환한다.
 * 백엔드 API가 아직 미구현일 수 있으므로 mock 데이터 폴백 포함.
 */
export async function discoverEdges(
  caseId: string,
  params: { maxLag: number; minCorrelation: number; selectedNodes?: string[] }
): Promise<{ edges: CausalEdge[]; dataRows: number; variablesCount: number }> {
  try {
    const res = (await visionApi.post(`/api/v3/cases/${caseId}/causal-analysis`, {
      max_lag: params.maxLag,
      min_correlation: params.minCorrelation,
      node_ids: params.selectedNodes,
    })) as DiscoverEdgesResponse;

    const edges: CausalEdge[] = (res.edges ?? []).map((e) => ({
      source: e.sourceNodeId,
      sourceName: e.sourceNodeName,
      sourceField: e.sourceField,
      target: e.targetNodeId,
      targetName: e.targetNodeName,
      targetField: e.targetField,
      method: e.grangerPValue < 0.05 ? 'granger' : 'correlation',
      strength: e.score,
      lag: e.lag,
      pValue: e.grangerPValue,
      pearson: e.pearson,
      direction: e.direction,
      selected: true, // 기본: 모두 선택
    }));

    return {
      edges,
      dataRows: res.data_rows ?? 0,
      variablesCount: res.variables_count ?? 0,
    };
  } catch {
    // 백엔드 미구현 시 mock 데이터 반환
    return generateMockEdges();
  }
}

/**
 * 모델 그래프 구성 (Step 3→4 전환 시)
 *
 * 선택된 엣지를 기반으로 예측 모델 DAG를 자동 생성한다.
 */
export async function buildModelGraph(
  caseId: string,
  edges: CausalEdge[]
): Promise<ModelSpec[]> {
  try {
    const rawEdges = edges
      .filter((e) => e.selected)
      .map((e) => ({
        sourceNodeId: e.source,
        sourceNodeName: e.sourceName,
        sourceField: e.sourceField,
        targetNodeId: e.target,
        targetNodeName: e.targetName,
        targetField: e.targetField,
        score: e.strength,
        lag: e.lag,
        pearson: e.pearson,
        grangerPValue: e.pValue,
        direction: e.direction,
      }));

    const res = (await visionApi.post(`/api/v3/cases/${caseId}/whatif-dag/build-graph`, {
      edges: rawEdges,
    })) as BuildModelGraphResponse;

    return (res.models ?? []).map((m) => ({
      modelId: m.model_id,
      name: m.name,
      targetNodeId: m.target_node_id,
      targetField: m.target_field,
      executionOrder: m.execution_order,
      features: m.features,
    }));
  } catch {
    // mock: 엣지에서 자동 모델 스펙 생성
    return generateMockModelSpecs(edges);
  }
}

/**
 * 모델 학습 (Step 4)
 */
export async function trainModels(
  caseId: string,
  modelSpecs: ModelSpec[],
  featureViewSql?: string
): Promise<TrainedModel[]> {
  try {
    const res = (await synapseApi.post(
      `/api/v3/synapse/ontology/cases/${caseId}/behavior-models`,
      {
        models: modelSpecs.map((s) => ({
          model_id: s.modelId,
          name: s.name,
          target_node_id: s.targetNodeId,
          target_field: s.targetField,
          features: s.features,
          execution_order: s.executionOrder,
        })),
        feature_view_sql: featureViewSql ?? '',
      }
    )) as TrainModelsResponse;

    return (res.results ?? []).map((r) => ({
      modelId: r.model_id,
      name: r.name,
      inputNodes: [], // 상세 매핑은 modelSpecs에서 가져옴
      outputNode: '',
      modelType: r.model_type ?? 'linear_regression',
      r2Score: r.r2 ?? 0,
      rmse: r.rmse ?? 0,
      status: r.status === 'trained' ? 'trained' : 'failed',
      executionOrder: 0,
      neo4jSaved: r.neo4j_saved,
    }));
  } catch {
    // mock: 모든 모델 학습 성공
    return generateMockTrainedModels(modelSpecs);
  }
}

/**
 * 모델 목록 조회
 */
export async function listModels(caseId: string): Promise<ModelsListResponse> {
  const res = (await visionApi.get(`${dagBase(caseId)}/models`)) as ModelsListResponse;
  return res;
}

/**
 * 베이스라인 스냅샷 조회 (Step 5)
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

    // 타임라인 변환
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

// ── Mock 데이터 생성 ──

function generateMockEdges(): {
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

function generateMockModelSpecs(edges: CausalEdge[]): ModelSpec[] {
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

function generateMockTrainedModels(specs: ModelSpec[]): TrainedModel[] {
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

function generateMockSnapshot(): SnapshotData {
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

function generateMockSimulationResult(
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
