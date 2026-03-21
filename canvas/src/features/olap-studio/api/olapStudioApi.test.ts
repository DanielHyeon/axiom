/**
 * OLAP Studio API 클라이언트 테스트.
 *
 * olapStudioApi.ts의 fetch wrapper와 각 API 네임스페이스
 * (dataSources, cubes, pivot, etlPipelines)를 검증한다.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { dataSources, cubes, pivot, etlPipelines } from './olapStudioApi';

// ─── fetch 모킹 ───────────────────────────────────────────

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch);
  mockFetch.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** 정상 JSON 응답을 생성한다 */
function okResponse(data: unknown) {
  return {
    ok: true,
    json: () => Promise.resolve({ data }),
  };
}

/** 에러 JSON 응답을 생성한다 */
function errorResponse(status: number, detail: string) {
  return {
    ok: false,
    status,
    statusText: `Error ${status}`,
    json: () => Promise.resolve({ detail }),
  };
}

// ─── dataSources API ──────────────────────────────────────

describe('dataSources API', () => {
  it('list: GET /data-sources 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse([{ id: '1', name: 'test-ds' }]));

    const result = await dataSources.list();

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/gateway/olap/data-sources',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
    );
    expect(result).toEqual([{ id: '1', name: 'test-ds' }]);
  });

  it('get: GET /data-sources/:id 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ id: 'ds-1', name: 'My DS' }));

    const result = await dataSources.get('ds-1');

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/gateway/olap/data-sources/ds-1',
      expect.anything(),
    );
    expect(result.name).toBe('My DS');
  });

  it('create: POST /data-sources 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ id: 'new', name: 'new-ds' }));

    await dataSources.create({
      name: 'new-ds',
      source_type: 'postgresql',
      connection_config: { host: 'localhost' },
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/gateway/olap/data-sources',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('delete: DELETE /data-sources/:id 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse(null));

    await dataSources.delete('ds-1');

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/gateway/olap/data-sources/ds-1',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('test: POST /data-sources/:id/test 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ status: 'healthy', message: 'OK' }));

    const result = await dataSources.test('ds-1');

    expect(result.status).toBe('healthy');
  });
});

// ─── cubes API ────────────────────────────────────────────

describe('cubes API', () => {
  it('list: GET /cubes 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse([{ id: 'c1', name: 'Sales' }]));

    const result = await cubes.list();

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/gateway/olap/cubes',
      expect.anything(),
    );
    expect(result).toHaveLength(1);
  });

  it('get: GET /cubes/:id 호출 — 차원/측정값 포함', async () => {
    const detail = {
      id: 'c1',
      name: 'Sales',
      dimensions: [{ id: 'd1', name: 'Time' }],
      measures: [{ id: 'm1', name: 'Revenue' }],
    };
    mockFetch.mockResolvedValueOnce(okResponse(detail));

    const result = await cubes.get('c1');

    expect(result.dimensions).toHaveLength(1);
    expect(result.measures).toHaveLength(1);
  });

  it('validate: POST /cubes/:id/validate 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ status: 'VALID', errors: [] }));

    const result = await cubes.validate('c1');

    expect(result.status).toBe('VALID');
    expect(result.errors).toEqual([]);
  });

  it('publish: POST /cubes/:id/publish 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ cube_id: 'c1', status: 'PUBLISHED' }));

    const result = await cubes.publish('c1');

    expect(result.status).toBe('PUBLISHED');
  });
});

// ─── pivot API ────────────────────────────────────────────

describe('pivot API', () => {
  it('execute: POST /pivot/execute — 결과 반환', async () => {
    const pivotResult = {
      sql: 'SELECT ...',
      columns: ['year', 'revenue'],
      rows: [['2025', 100000]],
      row_count: 1,
      execution_time_ms: 42,
    };
    mockFetch.mockResolvedValueOnce(okResponse(pivotResult));

    const result = await pivot.execute({ cubeName: 'Sales', measures: [{ name: 'revenue' }] });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/gateway/olap/pivot/execute',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(String),
      }),
    );
    expect(result.sql).toBe('SELECT ...');
    expect(result.row_count).toBe(1);
  });

  it('previewSql: POST /pivot/preview-sql — SQL만 반환', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ sql: 'SELECT year FROM dw.fact_table' }));

    const result = await pivot.previewSql({ cubeName: 'Sales', measures: [] });

    expect(result.sql).toContain('SELECT');
  });
});

// ─── etlPipelines API ────────────────────────────────────

describe('etlPipelines API', () => {
  it('list: GET /etl/pipelines 호출', async () => {
    mockFetch.mockResolvedValueOnce(okResponse([{ id: 'p1', name: 'ETL-1' }]));

    const result = await etlPipelines.list();

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/gateway/olap/etl/pipelines',
      expect.anything(),
    );
    expect(result).toHaveLength(1);
  });

  it('run: POST /etl/pipelines/:id/run — 실행 트리거', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ id: 'run-1', run_status: 'RUNNING' }));

    const result = await etlPipelines.run('p1');

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/gateway/olap/etl/pipelines/p1/run',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(result.run_status).toBe('RUNNING');
  });

  it('listRuns: GET /etl/pipelines/:id/runs — 실행 이력 조회', async () => {
    mockFetch.mockResolvedValueOnce(okResponse([
      { id: 'run-1', run_status: 'SUCCESS' },
      { id: 'run-2', run_status: 'FAILED' },
    ]));

    const result = await etlPipelines.listRuns('p1');

    expect(result).toHaveLength(2);
  });
});

// ─── 에러 처리 ────────────────────────────────────────────

describe('olapFetch 에러 처리', () => {
  it('API 오류 응답 시 detail 메시지를 포함한 Error를 던진다', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(400, '잘못된 요청'));

    await expect(dataSources.list()).rejects.toThrow('잘못된 요청');
  });

  it('API 오류 응답에서 JSON 파싱 실패 시 statusText 사용', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('parse error')),
    });

    await expect(cubes.list()).rejects.toThrow('Internal Server Error');
  });

  it('응답에 data 필드가 없으면 body 전체를 반환한다', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ sql: 'SELECT 1' }),
    });

    // data 필드가 없으므로 body 전체({ sql: 'SELECT 1' })가 반환됨
    const result = await pivot.previewSql({});
    expect(result).toEqual({ sql: 'SELECT 1' });
  });
});
