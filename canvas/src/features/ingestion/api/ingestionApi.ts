/**
 * 데이터 수집/파이프라인 Weaver API 호출 레이어
 * 엔드포인트: POST /api/v3/weaver/upload, GET /api/v3/weaver/pipelines 등
 */

import { weaverApi } from '@/lib/api/clients';
import { useAuthStore } from '@/stores/authStore';
import type {
  UploadResponse,
  UploadMetadata,
  PipelineListResponse,
  PipelineStatusResponse,
  Pipeline,
  IngestionHistoryResponse,
} from '../types/ingestion';

// ============================================================================
// 파일 업로드 API
// ============================================================================

/** Weaver 베이스 URL (SSE 스트림 등 raw fetch용) */
function getWeaverBaseUrl(): string {
  const u = import.meta.env.VITE_WEAVER_URL;
  if (!u) return 'http://localhost:8001';
  return String(u).replace(/\/$/, '');
}

/**
 * 파일 업로드 (multipart/form-data).
 * 진행률 콜백을 받아 XMLHttpRequest로 업로드한다.
 */
export function uploadFile(
  file: File,
  metadata: UploadMetadata = {},
  onProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const baseUrl = getWeaverBaseUrl();
    const token = useAuthStore.getState().accessToken;
    const formData = new FormData();
    formData.append('file', file);

    // 메타데이터 필드 추가
    if (metadata.datasourceName) formData.append('datasource_name', metadata.datasourceName);
    if (metadata.format) formData.append('format', metadata.format);
    if (metadata.delimiter) formData.append('delimiter', metadata.delimiter);
    if (metadata.encoding) formData.append('encoding', metadata.encoding);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${baseUrl}/api/v3/weaver/upload`);
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    // 진행률 이벤트
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        onProgress?.(percent);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText) as UploadResponse;
          resolve(data);
        } catch {
          resolve({ fileId: '', fileName: file.name, size: file.size });
        }
      } else {
        reject(new Error(`업로드 실패: HTTP ${xhr.status} — ${xhr.statusText}`));
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('업로드 중 네트워크 오류가 발생했습니다.'));
    });

    xhr.addEventListener('abort', () => {
      reject(new Error('업로드가 취소되었습니다.'));
    });

    xhr.send(formData);
  });
}

/**
 * 여러 파일 동시 업로드.
 * 개별 파일마다 onFileProgress 콜백 호출.
 */
export async function uploadFiles(
  files: File[],
  metadata: UploadMetadata = {},
  onFileProgress?: (fileIndex: number, percent: number) => void,
): Promise<UploadResponse[]> {
  const results: UploadResponse[] = [];
  // 순차 업로드 (서버 부하 방지)
  for (let i = 0; i < files.length; i++) {
    const res = await uploadFile(
      files[i],
      metadata,
      (percent) => onFileProgress?.(i, percent),
    );
    results.push(res);
  }
  return results;
}

// ============================================================================
// 파이프라인 API
// ============================================================================

/** 파이프라인 목록 조회 */
export async function listPipelines(): Promise<PipelineListResponse> {
  const res = await weaverApi.get('/api/v3/weaver/pipelines');
  const body = res as PipelineListResponse | undefined;
  return {
    pipelines: Array.isArray(body?.pipelines) ? body!.pipelines : [],
    total: body?.total ?? 0,
  };
}

/** 파이프라인 단건 조회 */
export async function getPipeline(id: string): Promise<Pipeline> {
  const res = await weaverApi.get(`/api/v3/weaver/pipelines/${encodeURIComponent(id)}`);
  return res as unknown as Pipeline;
}

/** 파이프라인 실행 */
export async function runPipeline(id: string): Promise<{ jobId: string }> {
  const res = await weaverApi.post(`/api/v3/weaver/pipelines/${encodeURIComponent(id)}/run`);
  return res as unknown as { jobId: string };
}

/** 파이프라인 중지 */
export async function stopPipeline(id: string): Promise<void> {
  await weaverApi.post(`/api/v3/weaver/pipelines/${encodeURIComponent(id)}/stop`);
}

/** 파이프라인 실행 상태 폴링 */
export async function getPipelineStatus(id: string): Promise<PipelineStatusResponse> {
  const res = await weaverApi.get(`/api/v3/weaver/pipelines/${encodeURIComponent(id)}/status`);
  return res as unknown as PipelineStatusResponse;
}

/** 파이프라인 생성 */
export async function createPipeline(payload: {
  name: string;
  datasourceId: string;
  schedule?: string;
}): Promise<Pipeline> {
  const res = await weaverApi.post('/api/v3/weaver/pipelines', payload);
  return res as unknown as Pipeline;
}

/** 파이프라인 삭제 */
export async function deletePipeline(id: string): Promise<void> {
  await weaverApi.delete(`/api/v3/weaver/pipelines/${encodeURIComponent(id)}`);
}

// ============================================================================
// 수집 이력 API
// ============================================================================

/** 수집 이력 조회 */
export async function listIngestionHistory(params?: {
  pipelineId?: string;
  limit?: number;
  offset?: number;
}): Promise<IngestionHistoryResponse> {
  const res = await weaverApi.get('/api/v3/weaver/ingestion/history', { params });
  const body = res as IngestionHistoryResponse | undefined;
  return {
    records: Array.isArray(body?.records) ? body!.records : [],
    total: body?.total ?? 0,
  };
}
