/**
 * Step 2: 데이터/노드 선택
 *
 * - 온톨로지 노드 검색 입력
 * - 노드 타입 필터 (KPI, Measure, Process, Resource)
 * - 선택된 노드 목록 + 제거 버튼
 * - 노드 수 표시
 */
import { useState, useMemo, useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Search, X, Database, Plus, Filter } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import type { OntologyNode, OntologyNodeType } from '../types/whatifWizard.types';

/** 노드 타입별 색상 매핑 */
const NODE_TYPE_COLORS: Record<OntologyNodeType, string> = {
  KPI: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  Measure: 'bg-green-500/15 text-green-400 border-green-500/30',
  Process: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  Resource: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
};

/** 노드 타입 필터 목록 */
const NODE_TYPE_FILTERS: { value: OntologyNodeType | null; label: string }[] = [
  { value: null, label: '전체' },
  { value: 'KPI', label: 'KPI' },
  { value: 'Measure', label: 'Measure' },
  { value: 'Process', label: 'Process' },
  { value: 'Resource', label: 'Resource' },
];

/**
 * 샘플 온톨로지 노드 목록
 * 실제로는 Synapse API에서 로드하지만, 백엔드 미구현 시 폴백으로 사용
 */
const SAMPLE_NODES: OntologyNode[] = [
  { id: 'kpi_oee', name: 'OEE (종합설비효율)', type: 'KPI', description: '설비 가용률 x 성능 x 품질' },
  { id: 'kpi_throughput', name: 'Throughput Rate', type: 'KPI', description: '단위 시간당 생산량' },
  { id: 'kpi_defect', name: 'Defect Rate', type: 'KPI', description: '불량률' },
  { id: 'kpi_downtime', name: 'Downtime', type: 'KPI', description: '가동 중단 시간' },
  { id: 'msr_availability', name: 'Availability', type: 'Measure', description: '설비 가용률' },
  { id: 'msr_performance', name: 'Performance', type: 'Measure', description: '성능 효율' },
  { id: 'msr_quality', name: 'Quality', type: 'Measure', description: '품질률' },
  { id: 'msr_cycle_time', name: 'Cycle Time', type: 'Measure', description: '사이클 타임' },
  { id: 'msr_mtbf', name: 'MTBF', type: 'Measure', description: '평균 고장 간격' },
  { id: 'prc_assembly', name: 'Assembly', type: 'Process', description: '조립 공정' },
  { id: 'prc_inspection', name: 'Inspection', type: 'Process', description: '검사 공정' },
  { id: 'prc_packaging', name: 'Packaging', type: 'Process', description: '포장 공정' },
  { id: 'prc_maintenance', name: 'Maintenance', type: 'Process', description: '유지보수' },
  { id: 'rsc_machine_a', name: 'Machine A', type: 'Resource', description: '주력 생산 설비' },
  { id: 'rsc_robot_01', name: 'Robot 01', type: 'Resource', description: '로봇 팔 #1' },
  { id: 'rsc_operator', name: 'Operator Team', type: 'Resource', description: '운영 인력' },
  { id: 'rsc_material', name: 'Raw Material', type: 'Resource', description: '원자재' },
];

export function Step2DataSelect() {
  const { t } = useTranslation();
  const {
    selectedNodes,
    selectedNodeIds,
    nodeSearchQuery,
    nodeTypeFilter,
    addNode,
    removeNode,
    setNodeSearchQuery,
    setNodeTypeFilter,
  } = useWhatIfWizardStore();

  // 로컬 검색 상태 (디바운스 대체)
  const [localQuery, setLocalQuery] = useState(nodeSearchQuery);

  // 검색 입력 핸들러
  const handleSearch = useCallback(
    (value: string) => {
      setLocalQuery(value);
      setNodeSearchQuery(value);
    },
    [setNodeSearchQuery],
  );

  // 필터링된 노드 목록
  const filteredNodes = useMemo(() => {
    let nodes = SAMPLE_NODES;

    // 타입 필터
    if (nodeTypeFilter) {
      nodes = nodes.filter((n) => n.type === nodeTypeFilter);
    }

    // 검색 필터
    if (localQuery.trim()) {
      const q = localQuery.toLowerCase();
      nodes = nodes.filter(
        (n) =>
          n.name.toLowerCase().includes(q) ||
          n.id.toLowerCase().includes(q) ||
          (n.description?.toLowerCase().includes(q) ?? false),
      );
    }

    // 이미 선택된 노드 제외
    return nodes.filter((n) => !selectedNodeIds.includes(n.id));
  }, [localQuery, nodeTypeFilter, selectedNodeIds]);

  return (
    <div className="space-y-6 max-w-3xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Database className="w-5 h-5 text-primary" />
          {t('whatifWizard.step2.title', '데이터 선택')}
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          {t(
            'whatifWizard.step2.description',
            '시뮬레이션에 포함할 온톨로지 노드를 선택하세요.',
          )}
        </p>
      </div>

      {/* 선택된 노드 표시 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">
              {t('whatifWizard.step2.selectedTitle', '선택된 노드')}
            </CardTitle>
            <Badge variant="secondary" className="text-xs">
              {selectedNodes.length}개 선택됨
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {selectedNodes.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              아래에서 노드를 검색하고 추가하세요.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {selectedNodes.map((node) => (
                <Badge
                  key={node.id}
                  variant="outline"
                  className={cn(
                    'pl-2 pr-1 py-1 text-xs flex items-center gap-1.5',
                    NODE_TYPE_COLORS[node.type],
                  )}
                >
                  <span className="font-mono text-[10px] opacity-60">{node.type}</span>
                  <span>{node.name}</span>
                  <button
                    type="button"
                    onClick={() => removeNode(node.id)}
                    className="ml-0.5 p-0.5 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                    aria-label={`${node.name} 제거`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 검색 + 필터 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Search className="w-4 h-4" />
            {t('whatifWizard.step2.searchTitle', '노드 검색')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 검색 입력 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder={t('whatifWizard.step2.searchPlaceholder', '노드 이름 또는 ID로 검색...')}
              value={localQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* 타입 필터 버튼 */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-muted-foreground shrink-0" />
            {NODE_TYPE_FILTERS.map((f) => (
              <Button
                key={f.label}
                variant={nodeTypeFilter === f.value ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs"
                onClick={() => setNodeTypeFilter(f.value)}
              >
                {f.label}
              </Button>
            ))}
          </div>

          {/* 검색 결과 노드 목록 */}
          <div className="max-h-64 overflow-y-auto space-y-1 border border-border rounded-lg p-2">
            {filteredNodes.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                {localQuery.trim()
                  ? '검색 결과가 없습니다.'
                  : '선택 가능한 노드가 없습니다.'}
              </p>
            ) : (
              filteredNodes.map((node) => (
                <button
                  key={node.id}
                  type="button"
                  onClick={() => addNode(node)}
                  className={cn(
                    'w-full flex items-center gap-3 p-2.5 rounded-md text-left transition-colors',
                    'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  )}
                >
                  {/* 타입 뱃지 */}
                  <Badge
                    variant="outline"
                    className={cn('text-[10px] shrink-0 w-16 justify-center', NODE_TYPE_COLORS[node.type])}
                  >
                    {node.type}
                  </Badge>

                  {/* 노드 정보 */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{node.name}</p>
                    {node.description && (
                      <p className="text-xs text-muted-foreground truncate">
                        {node.description}
                      </p>
                    )}
                  </div>

                  {/* 추가 아이콘 */}
                  <Plus className="w-4 h-4 text-muted-foreground shrink-0" />
                </button>
              ))
            )}
          </div>

          {/* 검색 결과 수 */}
          <p className="text-xs text-muted-foreground text-right">
            {filteredNodes.length}개 노드 표시 중
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
