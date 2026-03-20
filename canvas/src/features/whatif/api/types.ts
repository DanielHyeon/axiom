/**
 * Vision Wizard API 내부 타입 정의
 *
 * 백엔드 API 원형(raw) 응답 타입과 변환 헬퍼를 정의한다.
 * 각 API 모듈(discoveryApi, trainingApi, simulationApi)에서 공통으로 사용.
 */
import type { SimulationTrace } from '../types/wizard';

// ── 베이스 경로 생성 함수 ──
export const dagBase = (caseId: string) => `/api/v3/cases/${caseId}/whatif-dag`;

// ── 인과 분석 응답 타입 ──

export interface RawEdge {
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

export interface DiscoverEdgesResponse {
  edges: RawEdge[];
  data_rows: number;
  variables_count: number;
  feature_view_sql: string;
  field_descriptions?: Record<string, string>;
}

// ── 모델 그래프 구성 응답 타입 ──

export interface BuildModelGraphResponse {
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

// ── 모델 학습 응답 타입 ──

export interface TrainModelsResponse {
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

// ── 시뮬레이션 응답 타입 ──

export interface RawSimulationTrace {
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

export interface SimulateResponse {
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

// ── 스냅샷 응답 타입 ──

export interface SnapshotResponse {
  success: boolean;
  case_id: string;
  snapshot_date: string | null;
  data: Record<string, number>;
  variable_count: number;
}

// ── 모델 목록 응답 타입 ──

export interface ModelsListResponse {
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

// ── 변환 헬퍼: 백엔드 원형 → 프론트엔드 타입 ──

/** RawSimulationTrace를 프론트엔드 SimulationTrace 타입으로 변환 */
export function rawTraceToTrace(raw: RawSimulationTrace): SimulationTrace {
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
