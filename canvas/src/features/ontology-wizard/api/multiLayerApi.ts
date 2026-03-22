/**
 * Deep Agents 멀티레이어 온톨로지 생성 API
 * SSE 스트리밍 + 동기 버전 제공
 */
import { synapseApi } from '@/lib/api/clients';
import { createNdjsonStream, type StreamOptions } from '@/lib/api/streamManager';
import type { TargetLayer, GenerationResult, LayerSchema } from '../types/wizard';

// ─── 요청/응답 인터페이스 ───

/** 멀티레이어 생성 요청 본문 */
export interface MultiLayerRequest {
  /** 입력 텍스트 (도메인 설명, 문서 내용 등) */
  input_text: string;
  /** 도메인 힌트 (예: "제조업", "금융") */
  domain_hint?: string;
  /** 대상 레이어 목록 */
  target_layers?: TargetLayer[];
  /** 병렬 생성 여부 */
  parallel: boolean;
}

/** SSE 이벤트 타입 (NDJSON 스트림에서 수신) */
export type MultiLayerEvent =
  | { event: 'start'; target_layers: string[] }
  | { event: 'layer_progress'; layer: string; progress: number; message: string }
  | { event: 'layer_complete'; layer: string; node_count: number; relation_count: number }
  | { event: 'complete'; data: MultiLayerCompleteData }
  | { event: 'error'; message: string };

/** 완료 이벤트의 데이터 구조 */
export interface MultiLayerCompleteData {
  layer_schemas: Array<{
    layer: string;
    nodes: Array<{ id: string; label: string; layer: string; properties: Record<string, unknown> }>;
    relations: Array<{ source: string; target: string; type: string; properties?: Record<string, unknown> }>;
  }>;
  total_nodes: number;
  total_relations: number;
}

/** 동기 API 응답 */
interface MultiLayerSyncResponse {
  success: boolean;
  data: MultiLayerCompleteData;
}

// ─── SSE 스트리밍 콜백 인터페이스 ───

export interface MultiLayerCallbacks {
  /** 스트림 시작 (대상 레이어 목록 수신) */
  onStart?: (targetLayers: string[]) => void;
  /** 레이어 진행 상황 업데이트 */
  onLayerProgress?: (layer: string, progress: number, message: string) => void;
  /** 레이어 생성 완료 */
  onLayerComplete?: (layer: string, nodeCount: number, relationCount: number) => void;
  /** 전체 생성 완료 */
  onComplete?: (result: GenerationResult) => void;
  /** 에러 발생 */
  onError?: (error: Error) => void;
}

// ─── Synapse 베이스 URL 추출 ───

/** synapseApi에서 baseURL 추출 (스트리밍용) */
function getSynapseBaseUrl(): string {
  const defaults = synapseApi.defaults;
  return (defaults.baseURL ?? 'http://localhost:9003').replace(/\/$/, '');
}

// ─── 서버 응답 → 프론트 타입 변환 ───

function mapCompleteData(data: MultiLayerCompleteData): GenerationResult {
  const layerSchemas: LayerSchema[] = data.layer_schemas.map((ls) => ({
    layer: ls.layer,
    nodes: ls.nodes,
    relations: ls.relations,
  }));
  return {
    layerSchemas,
    totalNodes: data.total_nodes,
    totalRelations: data.total_relations,
  };
}

// ─── API 함수 ───

/**
 * SSE 스트리밍 방식으로 멀티레이어 온톨로지 생성
 * @returns AbortController (취소용)
 */
export async function streamMultiLayerGeneration(
  params: MultiLayerRequest,
  callbacks: MultiLayerCallbacks,
): Promise<AbortController> {
  const url = `${getSynapseBaseUrl()}/api/v3/synapse/ontology/generate-multi-layer`;

  const streamCallbacks: StreamOptions<MultiLayerEvent> = {
    onMessage: (event) => {
      switch (event.event) {
        case 'start':
          callbacks.onStart?.(event.target_layers);
          break;
        case 'layer_progress':
          callbacks.onLayerProgress?.(event.layer, event.progress, event.message);
          break;
        case 'layer_complete':
          callbacks.onLayerComplete?.(event.layer, event.node_count, event.relation_count);
          break;
        case 'complete':
          callbacks.onComplete?.(mapCompleteData(event.data));
          break;
        case 'error':
          callbacks.onError?.(new Error(event.message));
          break;
      }
    },
    onComplete: () => {
      // 스트림이 정상 종료됨 (complete 이벤트가 이미 처리됨)
    },
    onError: (error) => {
      callbacks.onError?.(error);
    },
  };

  return createNdjsonStream<MultiLayerEvent>(url, params as unknown as Record<string, unknown>, streamCallbacks);
}

/**
 * 동기 방식으로 멀티레이어 온톨로지 생성
 * SSE 없이 한 번에 결과를 반환
 */
export async function generateMultiLayerSync(
  params: MultiLayerRequest,
): Promise<GenerationResult> {
  const res = (await synapseApi.post(
    '/api/v3/synapse/ontology/generate-multi-layer/sync',
    params,
  )) as unknown as MultiLayerSyncResponse;

  return mapCompleteData(res.data);
}
