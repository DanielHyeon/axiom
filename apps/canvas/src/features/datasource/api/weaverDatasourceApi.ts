import { weaverApi } from '@/lib/api/clients';

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
