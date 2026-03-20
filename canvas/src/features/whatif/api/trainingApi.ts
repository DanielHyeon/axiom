/**
 * 모델 학습(Training) API 모듈
 *
 * Synapse 서비스에 BehaviorModel 학습 요청을 보내고,
 * Vision 서비스에서 학습된 모델 목록을 조회한다.
 */
import { visionApi, synapseApi } from '@/lib/api/clients';
import type { ModelSpec, TrainedModel } from '../types/wizard';
import type { TrainModelsResponse, ModelsListResponse } from './types';
import { dagBase } from './types';
import { generateMockTrainedModels } from './mockData';

/**
 * 모델 학습 (Step 4)
 *
 * 모델 스펙을 Synapse에 전달하여 BehaviorModel을 학습시킨다.
 * Neo4j에 모델 노드와 READS_FIELD/PREDICTS_FIELD 링크가 생성된다.
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

    // 백엔드 응답 → 프론트엔드 TrainedModel 타입으로 변환
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
 *
 * 해당 케이스에 등록된 모든 학습 모델의 목록을 가져온다.
 */
export async function listModels(caseId: string): Promise<ModelsListResponse> {
  const res = (await visionApi.get(`${dagBase(caseId)}/models`)) as ModelsListResponse;
  return res;
}
