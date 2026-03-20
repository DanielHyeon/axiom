/**
 * 인과 분석(Discovery) API 모듈
 *
 * Vision 서비스에 인과 관계 발견을 요청하고,
 * 발견된 엣지를 기반으로 예측 모델 DAG를 자동 구성한다.
 */
import { visionApi } from '@/lib/api/clients';
import type { CausalEdge, ModelSpec } from '../types/wizard';
import type { DiscoverEdgesResponse, BuildModelGraphResponse } from './types';
import { generateMockEdges, generateMockModelSpecs } from './mockData';

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

    // 백엔드 원형 → 프론트엔드 타입으로 변환
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
    // 프론트엔드 타입 → 백엔드 원형으로 변환
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
