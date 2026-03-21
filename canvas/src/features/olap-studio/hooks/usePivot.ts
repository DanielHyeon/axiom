/**
 * 피벗 분석 훅 — 큐브 선택, 피벗 설정, SQL 실행을 관리한다.
 */
import { useState, useCallback } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { cubes, pivot, type Cube, type PivotResult } from '../api/olapStudioApi';

// 기존 소비자와의 호환성을 위해 PivotResult를 재-export
export type { PivotResult } from '../api/olapStudioApi';

// ─── 피벗 필드 타입 ───────────────────────────────────────

export interface PivotField {
  dimension: string;
  level: string;
}

export interface PivotMeasure {
  name: string;
  aggregator: string;
}

export interface PivotFilter {
  dimension: string;
  level: string;
  operator: string;
  value: string | string[];
}

export interface PivotConfig {
  rows: PivotField[];
  columns: PivotField[];
  measures: PivotMeasure[];
  filters: PivotFilter[];
}

// ─── 피벗 요청 본문 빌더 ──────────────────────────────────

/** 피벗 API 요청 본문을 생성한다 */
function buildPivotBody(cubeName: string, config: PivotConfig) {
  return {
    cubeName,
    rows: config.rows,
    columns: config.columns,
    measures: config.measures,
    filters: config.filters,
    limit: 1000,
  };
}

// ─── 훅 ───────────────────────────────────────────────────

const EMPTY_CONFIG: PivotConfig = { rows: [], columns: [], measures: [], filters: [] };

export function usePivot() {
  const [selectedCubeId, setSelectedCubeId] = useState<string | null>(null);
  const [selectedCubeName, setSelectedCubeName] = useState('');
  const [config, setConfig] = useState<PivotConfig>(EMPTY_CONFIG);
  const [result, setResult] = useState<PivotResult | null>(null);
  const [previewSql, setPreviewSql] = useState('');

  // 큐브 목록
  const cubeList = useQuery({
    queryKey: ['olap', 'cubes'],
    queryFn: cubes.list,
  });

  // 큐브 선택 — 설정과 결과를 초기화한다
  const selectCube = useCallback((cube: Cube) => {
    setSelectedCubeId(cube.id);
    setSelectedCubeName(cube.name);
    setConfig(EMPTY_CONFIG);
    setResult(null);
    setPreviewSql('');
  }, []);

  // ─── 피벗 설정 변경 핸들러 ──────────────────────────────

  const addRow = useCallback((field: PivotField) => {
    setConfig((prev) => ({ ...prev, rows: [...prev.rows, field] }));
  }, []);

  const removeRow = useCallback((idx: number) => {
    setConfig((prev) => ({ ...prev, rows: prev.rows.filter((_, i) => i !== idx) }));
  }, []);

  const addColumn = useCallback((field: PivotField) => {
    setConfig((prev) => ({ ...prev, columns: [...prev.columns, field] }));
  }, []);

  const removeColumn = useCallback((idx: number) => {
    setConfig((prev) => ({ ...prev, columns: prev.columns.filter((_, i) => i !== idx) }));
  }, []);

  const addMeasure = useCallback((measure: PivotMeasure) => {
    setConfig((prev) => ({ ...prev, measures: [...prev.measures, measure] }));
  }, []);

  const removeMeasure = useCallback((idx: number) => {
    setConfig((prev) => ({ ...prev, measures: prev.measures.filter((_, i) => i !== idx) }));
  }, []);

  const addFilter = useCallback((filter: PivotFilter) => {
    setConfig((prev) => ({ ...prev, filters: [...prev.filters, filter] }));
  }, []);

  const removeFilter = useCallback((idx: number) => {
    setConfig((prev) => ({ ...prev, filters: prev.filters.filter((_, i) => i !== idx) }));
  }, []);

  // ─── 실행 뮤테이션 ─────────────────────────────────────

  // 공유 API 클라이언트를 통한 피벗 실행
  const executeMut = useMutation({
    mutationFn: () => pivot.execute(buildPivotBody(selectedCubeName, config)),
    onSuccess: (data) => setResult(data),
    onError: (err: Error) => {
      setResult({
        sql: '',
        columns: [],
        rows: [],
        row_count: 0,
        execution_time_ms: 0,
        error: err.message,
      });
    },
  });

  // 공유 API 클라이언트를 통한 SQL 미리보기
  const previewMut = useMutation({
    mutationFn: () => pivot.previewSql(buildPivotBody(selectedCubeName, config)).then((r) => r.sql),
    onSuccess: (sql) => setPreviewSql(sql),
  });

  return {
    cubeList,
    selectedCubeId,
    selectedCubeName,
    selectCube,
    config,
    addRow,
    removeRow,
    addColumn,
    removeColumn,
    addMeasure,
    removeMeasure,
    addFilter,
    removeFilter,
    result,
    previewSql,
    execute: executeMut.mutate,
    isExecuting: executeMut.isPending,
    preview: previewMut.mutate,
    isPreviewing: previewMut.isPending,
  };
}
