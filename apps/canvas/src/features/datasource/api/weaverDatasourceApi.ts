import { weaverApi } from '@/lib/api/clients';
import { useAuthStore } from '@/stores/authStore';

export interface DatasourceItem {
  name: string;
  engine: string;
  status: string;
  description?: string;
  tables_count?: number;
  metadata_extracted?: boolean;
}

export interface DatasourceCreatePayload {
  name: string;
  engine: string;
  connection: Record<string, unknown>;
  description?: string;
}

export interface EngineType {
  engine: string;
  label: string;
  icon?: string;
  connection_schema?: Record<string, unknown>;
  supports_metadata_extraction?: boolean;
}

async function normalize<T>(res: unknown): Promise<T> {
  return res as T;
}

export async function listDatasources(): Promise<{ datasources: DatasourceItem[]; total: number }> {
  const res = await weaverApi.get('/api/datasources');
  const body = (res as { datasources?: DatasourceItem[]; total?: number }) ?? {};
  return {
    datasources: Array.isArray(body.datasources) ? body.datasources : [],
    total: typeof body.total === 'number' ? body.total : 0,
  };
}

export async function getDatasource(name: string): Promise<Record<string, unknown>> {
  return normalize(weaverApi.get(`/api/datasources/${encodeURIComponent(name)}`));
}

export async function createDatasource(payload: DatasourceCreatePayload): Promise<{ name: string }> {
  const res = await weaverApi.post('/api/datasources', payload);
  return res as unknown as { name: string };
}

export async function deleteDatasource(name: string): Promise<void> {
  await weaverApi.delete(`/api/datasources/${encodeURIComponent(name)}`);
}

export async function testConnection(name: string): Promise<{ status: string; message?: string }> {
  const res = await weaverApi.post(`/api/datasources/${encodeURIComponent(name)}/test`);
  return res as unknown as { status: string; message?: string };
}

export async function getDatasourceSchemas(name: string): Promise<{ datasource: string; schemas: string[] }> {
  const res = await weaverApi.get(`/api/datasources/${encodeURIComponent(name)}/schemas`);
  return res as unknown as { datasource: string; schemas: string[] };
}

export async function getDatasourceTables(name: string, schema: string): Promise<{ datasource: string; schema: string; tables: string[] }> {
  const res = await weaverApi.get(`/api/datasources/${encodeURIComponent(name)}/tables`, { params: { schema } });
  return res as unknown as { datasource: string; schema: string; tables: string[] };
}

export async function getDatasourceTypes(): Promise<{ types: EngineType[] }> {
  const res = await weaverApi.get('/api/datasources/types');
  const body = (res as { types?: EngineType[] }) ?? {};
  return { types: Array.isArray(body.types) ? body.types : [] };
}

/** Legacy sync (POST /datasource/{ds_id}/sync). Returns job_id. */
export async function triggerSync(dsId: string): Promise<{ status: string; job_id: string; datasource_id: string }> {
  const res = await weaverApi.post(`/datasource/${encodeURIComponent(dsId)}/sync`);
  return res as unknown as { status: string; job_id: string; datasource_id: string };
}

export interface JobItem {
  id: string;
  datasource_id?: string;
  status?: string;
  type?: string;
  created_at?: string;
}

export async function listJobs(): Promise<{ jobs: JobItem[] }> {
  const res = await weaverApi.get('/api/query/jobs');
  const body = (res as { jobs?: JobItem[] }) ?? {};
  return { jobs: Array.isArray(body.jobs) ? body.jobs : [] };
}

// --- extract-metadata SSE (Weaver POST /api/datasources/{name}/extract-metadata) ---

export interface ExtractMetadataPayload {
  schemas?: string[] | null;
  include_sample_data?: boolean;
  sample_limit?: number;
  include_row_counts?: boolean;
}

export interface ExtractMetadataProgressData {
  phase?: string;
  percent?: number;
  completed?: number;
  total?: number;
  current_schema?: string;
  current_table?: string;
}

export interface ExtractMetadataCallbacks {
  onProgress?: (data: ExtractMetadataProgressData & Record<string, unknown>) => void;
  onComplete?: (data: Record<string, unknown>) => void;
  onNeo4jSaved?: (data: Record<string, unknown>) => void;
  onError?: (data: { message?: string; code?: string }) => void;
}

function getWeaverBaseUrl(): string {
  const u = import.meta.env.VITE_WEAVER_URL;
  if (!u) return 'http://localhost:8001';
  return String(u).replace(/\/$/, '');
}

/**
 * POST /api/datasources/{name}/extract-metadata SSE 스트림 구독.
 * progress/complete/neo4j_saved/error 이벤트로 콜백 호출. 완료 시 resolve, error 이벤트 또는 네트워크 오류 시 reject.
 */
export function extractMetadataStream(
  name: string,
  payload: ExtractMetadataPayload = {},
  callbacks: ExtractMetadataCallbacks = {}
): Promise<void> {
  const baseUrl = getWeaverBaseUrl();
  const token = useAuthStore.getState().accessToken;
  const url = `${baseUrl}/api/datasources/${encodeURIComponent(name)}/extract-metadata`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  return new Promise((resolve, reject) => {
    let buffer = '';
    fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        schemas: payload.schemas ?? undefined,
        include_sample_data: payload.include_sample_data ?? false,
        sample_limit: payload.sample_limit ?? 5,
        include_row_counts: payload.include_row_counts !== false,
      }),
    })
      .then((res) => {
        if (!res.ok) {
          res.text().then((t) => reject(new Error(t || `HTTP ${res.status}`)));
          return;
        }
        const reader = res.body?.getReader();
        if (!reader) {
          reject(new Error('No response body'));
          return;
        }
        const decoder = new TextDecoder();
        function read(): Promise<void> {
          return reader.read().then(({ done, value }) => {
            if (done) {
              resolve();
              return;
            }
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split(/\n\n/);
            buffer = parts.pop() ?? '';
            for (const block of parts) {
              let event = '';
              let dataStr = '';
              for (const line of block.split(/\n/)) {
                if (line.startsWith('event:')) event = line.slice(6).trim();
                else if (line.startsWith('data:')) dataStr = line.slice(5).trim();
              }
              try {
                const data = dataStr ? (JSON.parse(dataStr) as Record<string, unknown>) : {};
                if (event === 'progress') callbacks.onProgress?.(data as ExtractMetadataProgressData & Record<string, unknown>);
                else if (event === 'complete') callbacks.onComplete?.(data);
                else if (event === 'neo4j_saved') callbacks.onNeo4jSaved?.(data);
                else if (event === 'error') {
                  callbacks.onError?.(data as { message?: string; code?: string });
                  reject(new Error((data as { message?: string }).message || 'extract-metadata error'));
                  return;
                }
              } catch (e) {
                // ignore parse errors for unknown events
              }
            }
            return read();
          });
        }
        return read();
      })
      .catch(reject);
  });
}
