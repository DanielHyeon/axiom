import { visionApi } from '@/lib/api/clients';
import type { CubeDefinition } from '../types/olap';

const PREFIX = '/api/v3';

/** Vision GET /api/v3/cubes 응답 */
interface VisionCubeRow {
  name: string;
  fact_table?: string;
  dimensions?: string[];
  measures?: string[];
}

/** Vision GET /api/v3/cubes/{name} 응답 */
interface VisionCubeDetail {
  name: string;
  fact_table: string;
  dimensions: { name: string; levels?: { name: string; type?: string }[] }[];
  measures: { name: string; column?: string; aggregator?: string }[];
}

/** Vision POST /api/v3/pivot/query 요청 */
export interface PivotQueryParams {
  cube_name: string;
  rows: string[];
  columns: string[];
  measures: string[];
  filters?: { dimension_level: string; operator: string; values: unknown[] }[];
  limit?: number;
  offset?: number;
}

/** Vision POST /api/v3/pivot/query 응답 */
export interface PivotQueryResponse {
  cube_name: string;
  generated_sql?: string;
  execution_time_ms: number;
  total_rows: number;
  columns: { name: string; type: string }[];
  rows: Record<string, unknown>[];
  aggregations?: Record<string, number>;
}

export async function listCubes(): Promise<CubeDefinition[]> {
  const res = (await visionApi.get(PREFIX + '/cubes')) as { cubes: VisionCubeRow[] };
  const cubes = res?.cubes ?? [];
  return cubes.map((c) => ({
    id: c.name,
    name: c.name,
    description: c.fact_table ? `Fact: ${c.fact_table}` : '',
    dimensions: (c.dimensions ?? []).map((d) => ({ id: d, name: d, type: 'string' as const })),
    measures: (c.measures ?? []).map((m) => ({ id: m, name: m, aggregation: 'sum' as const })),
  }));
}

export async function getCube(cubeName: string): Promise<CubeDefinition | null> {
  try {
    const c = (await visionApi.get(PREFIX + `/cubes/${encodeURIComponent(cubeName)}`)) as VisionCubeDetail;
    return {
      id: c.name,
      name: c.name,
      description: c.fact_table ? `Fact: ${c.fact_table}` : '',
      dimensions: (c.dimensions ?? []).map((d) => ({ id: d.name, name: d.name, type: 'string' as const })),
      measures: (c.measures ?? []).map((m) => ({
        id: m.name,
        name: m.name,
        aggregation: (m.aggregator as 'sum') || 'sum',
      })),
    };
  } catch {
    return null;
  }
}

export async function pivotQuery(params: PivotQueryParams): Promise<PivotQueryResponse> {
  const res = (await visionApi.post(PREFIX + '/pivot/query', params)) as PivotQueryResponse;
  return res;
}
