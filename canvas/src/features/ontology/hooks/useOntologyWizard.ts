/**
 * useOntologyWizard — 온톨로지 위자드 3단계 로직 훅
 * Step 1: DB 스키마 선택 (데이터소스 → 스키마 → 테이블)
 * Step 2: 레이어 매핑 (각 테이블 → KPI/Driver/Measure/Process/Resource)
 * Step 3: 검토 + 생성 (미리보기 → Synapse API 호출)
 */
import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { weaverApi, synapseApi } from '@/lib/api/clients';
import type { OntologyLayer } from '../types/ontology';

// ─── 타입 정의 ─────────────────────────────────

export type WizardStep = 'schema' | 'mapping' | 'review';

export interface DatasourceItem {
  name: string;
  type?: string;
}

export interface SchemaItem {
  name: string;
  tableCount?: number;
}

export interface TableItem {
  name: string;
  columnCount?: number;
  columns?: string[];
}

export interface TableMapping {
  tableName: string;
  layer: OntologyLayer;
  columns?: string[];
  description?: string;
}

export interface GeneratedNode {
  id: string;
  name: string;
  layer: OntologyLayer;
  sourceTable: string;
  properties: Record<string, string>;
}

export interface GeneratedRelationship {
  source: string;
  target: string;
  type: string;
}

export interface GenerationResult {
  nodes: GeneratedNode[];
  relationships: GeneratedRelationship[];
  tablesProcessed: number;
}

// ─── Mock 데이터 (백엔드 미구현 시) ────────────

const MOCK_DATASOURCES: DatasourceItem[] = [
  { name: 'insolvency_os', type: 'PostgreSQL' },
  { name: 'analytics_db', type: 'PostgreSQL' },
];

const MOCK_SCHEMAS: SchemaItem[] = [
  { name: 'core', tableCount: 8 },
  { name: 'synapse', tableCount: 5 },
  { name: 'weaver', tableCount: 6 },
  { name: 'oracle', tableCount: 4 },
  { name: 'vision', tableCount: 3 },
];

const MOCK_TABLES: TableItem[] = [
  { name: 'kpi_targets', columnCount: 6, columns: ['id', 'name', 'target_value', 'unit', 'period', 'created_at'] },
  { name: 'measures', columnCount: 5, columns: ['id', 'name', 'value', 'kpi_id', 'timestamp'] },
  { name: 'processes', columnCount: 7, columns: ['id', 'name', 'status', 'type', 'owner', 'start_date', 'end_date'] },
  { name: 'equipment', columnCount: 5, columns: ['id', 'name', 'type', 'status', 'process_id'] },
  { name: 'sensors', columnCount: 6, columns: ['id', 'name', 'equipment_id', 'unit', 'min_value', 'max_value'] },
  { name: 'operators', columnCount: 4, columns: ['id', 'name', 'role', 'shift'] },
];

// 자동 레이어 추천 로직 — 테이블/컬럼 이름 기반 휴리스틱
function guessLayer(tableName: string): OntologyLayer {
  const name = tableName.toLowerCase();
  if (name.includes('kpi') || name.includes('target') || name.includes('metric')) return 'kpi';
  if (name.includes('driver') || name.includes('cause') || name.includes('factor')) return 'driver';
  if (name.includes('measure') || name.includes('indicator') || name.includes('score')) return 'measure';
  if (name.includes('process') || name.includes('workflow') || name.includes('step')) return 'process';
  return 'resource'; // 기본값: 리소스
}

// ─── 훅 ─────────────────────────────────────────

export function useOntologyWizard() {
  const queryClient = useQueryClient();

  // 현재 단계
  const [step, setStep] = useState<WizardStep>('schema');

  // Step 1 상태: 데이터소스/스키마/테이블 선택
  const [selectedDatasource, setSelectedDatasource] = useState('');
  const [selectedSchema, setSelectedSchema] = useState('');
  const [selectedTables, setSelectedTables] = useState<string[]>([]);

  // Step 2 상태: 테이블 → 레이어 매핑
  const [mappings, setMappings] = useState<TableMapping[]>([]);

  // Step 3 상태: 생성 옵션
  const [ontologyName, setOntologyName] = useState('');
  const [ontologyDescription, setOntologyDescription] = useState('');
  const [inferCausal, setInferCausal] = useState(true);

  // ─── 데이터소스 목록 ────────────────────────

  const datasourcesQuery = useQuery({
    queryKey: ['wizard', 'datasources'],
    queryFn: async (): Promise<DatasourceItem[]> => {
      try {
        const res = await weaverApi.get('/api/v3/weaver/datasources');
        const data = res as unknown as DatasourceItem[] | string[];
        return Array.isArray(data)
          ? data.map((d) => (typeof d === 'string' ? { name: d } : d))
          : MOCK_DATASOURCES;
      } catch {
        return MOCK_DATASOURCES;
      }
    },
    staleTime: 60_000,
  });

  // ─── 스키마 목록 ────────────────────────────

  const schemasQuery = useQuery({
    queryKey: ['wizard', 'schemas', selectedDatasource],
    queryFn: async (): Promise<SchemaItem[]> => {
      if (!selectedDatasource) return [];
      try {
        const res = await weaverApi.get(
          `/api/v3/weaver/datasources/${encodeURIComponent(selectedDatasource)}/schemas`,
        );
        const data = res as unknown as SchemaItem[] | string[];
        return Array.isArray(data)
          ? data.map((s) => (typeof s === 'string' ? { name: s } : s))
          : MOCK_SCHEMAS;
      } catch {
        return MOCK_SCHEMAS;
      }
    },
    enabled: !!selectedDatasource,
    staleTime: 60_000,
  });

  // ─── 테이블 목록 ────────────────────────────

  const tablesQuery = useQuery({
    queryKey: ['wizard', 'tables', selectedDatasource, selectedSchema],
    queryFn: async (): Promise<TableItem[]> => {
      if (!selectedDatasource || !selectedSchema) return [];
      try {
        const res = await weaverApi.get(
          `/api/v3/weaver/datasources/${encodeURIComponent(selectedDatasource)}/schemas/${encodeURIComponent(selectedSchema)}/tables`,
        );
        const data = res as unknown as TableItem[] | string[];
        return Array.isArray(data)
          ? data.map((t) => (typeof t === 'string' ? { name: t } : t))
          : MOCK_TABLES;
      } catch {
        return MOCK_TABLES;
      }
    },
    enabled: !!selectedDatasource && !!selectedSchema,
    staleTime: 60_000,
  });

  // ─── 테이블 선택 토글 ──────────────────────

  const toggleTable = useCallback(
    (tableName: string) => {
      setSelectedTables((prev) =>
        prev.includes(tableName) ? prev.filter((t) => t !== tableName) : [...prev, tableName],
      );
    },
    [],
  );

  const selectAllTables = useCallback(() => {
    const all = tablesQuery.data?.map((t) => t.name) ?? [];
    setSelectedTables(all);
  }, [tablesQuery.data]);

  const deselectAllTables = useCallback(() => {
    setSelectedTables([]);
  }, []);

  // ─── Step 1 → 2 전환: 자동 매핑 생성 ──────

  const goToMapping = useCallback(() => {
    const tables = tablesQuery.data ?? [];
    const newMappings: TableMapping[] = selectedTables.map((name) => {
      const table = tables.find((t) => t.name === name);
      return {
        tableName: name,
        layer: guessLayer(name),
        columns: table?.columns,
      };
    });
    setMappings(newMappings);
    setStep('mapping');
  }, [selectedTables, tablesQuery.data]);

  // ─── 매핑 레이어 변경 ──────────────────────

  const updateMappingLayer = useCallback((tableName: string, layer: OntologyLayer) => {
    setMappings((prev) =>
      prev.map((m) => (m.tableName === tableName ? { ...m, layer } : m)),
    );
  }, []);

  // ─── Step 2 → 3 전환 ──────────────────────

  const goToReview = useCallback(() => {
    if (!ontologyName && selectedSchema) {
      setOntologyName(`${selectedSchema.charAt(0).toUpperCase() + selectedSchema.slice(1)} Ontology`);
    }
    setStep('review');
  }, [ontologyName, selectedSchema]);

  // ─── 온톨로지 생성 뮤테이션 ────────────────

  const generateMutation = useMutation({
    mutationFn: async (): Promise<GenerationResult> => {
      try {
        const res = await synapseApi.post('/api/v3/synapse/ontology/generate-from-schema', {
          datasource: selectedDatasource,
          schema_name: selectedSchema,
          ontology_name: ontologyName,
          ontology_description: ontologyDescription,
          mappings: mappings.map((m) => ({
            table_name: m.tableName,
            layer: m.layer,
            description: m.description,
          })),
          infer_causal_relations: inferCausal,
        });
        return res as unknown as GenerationResult;
      } catch {
        // Mock: 매핑 기반으로 노드/관계 생성
        const nodes: GeneratedNode[] = mappings.map((m, i) => ({
          id: `gen-${i}`,
          name: m.tableName.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
          layer: m.layer,
          sourceTable: `${selectedSchema}.${m.tableName}`,
          properties: { source_table: m.tableName },
        }));

        // 간단한 관계 추론: KPI←Measure, Measure←Process, Process←Resource
        const layerOrder: OntologyLayer[] = ['kpi', 'driver', 'measure', 'process', 'resource'];
        const relationships: GeneratedRelationship[] = [];
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const srcIdx = layerOrder.indexOf(nodes[i].layer);
            const tgtIdx = layerOrder.indexOf(nodes[j].layer);
            if (tgtIdx === srcIdx + 1 || tgtIdx === srcIdx + 2) {
              relationships.push({
                source: nodes[j].id,
                target: nodes[i].id,
                type: 'DERIVED_FROM',
              });
            }
          }
        }

        return { nodes, relationships, tablesProcessed: mappings.length };
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ontology'] });
    },
  });

  // ─── 단계 뒤로 가기 ────────────────────────

  const goBack = useCallback(() => {
    if (step === 'mapping') setStep('schema');
    else if (step === 'review') setStep('mapping');
  }, [step]);

  // ─── 초기화 ────────────────────────────────

  const reset = useCallback(() => {
    setStep('schema');
    setSelectedDatasource('');
    setSelectedSchema('');
    setSelectedTables([]);
    setMappings([]);
    setOntologyName('');
    setOntologyDescription('');
    setInferCausal(true);
    generateMutation.reset();
  }, [generateMutation]);

  return {
    // 현재 단계
    step,
    setStep,
    goBack,
    reset,

    // Step 1: 스키마 선택
    datasources: datasourcesQuery.data ?? [],
    datasourcesLoading: datasourcesQuery.isLoading,
    selectedDatasource,
    setSelectedDatasource: (ds: string) => {
      setSelectedDatasource(ds);
      setSelectedSchema('');
      setSelectedTables([]);
    },
    schemas: schemasQuery.data ?? [],
    schemasLoading: schemasQuery.isLoading,
    selectedSchema,
    setSelectedSchema: (s: string) => {
      setSelectedSchema(s);
      setSelectedTables([]);
    },
    tables: tablesQuery.data ?? [],
    tablesLoading: tablesQuery.isLoading,
    selectedTables,
    toggleTable,
    selectAllTables,
    deselectAllTables,
    goToMapping,

    // Step 2: 레이어 매핑
    mappings,
    updateMappingLayer,
    goToReview,

    // Step 3: 검토 + 생성
    ontologyName,
    setOntologyName,
    ontologyDescription,
    setOntologyDescription,
    inferCausal,
    setInferCausal,
    generate: generateMutation.mutate,
    isGenerating: generateMutation.isPending,
    generationResult: generateMutation.data,
    generationError: generateMutation.error,
  };
}
