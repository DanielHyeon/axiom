/**
 * Step 2: 데이터 소스/기간 선택
 *
 * - 날짜 범위 선택
 * - 분석 대상 노드 선택 (온톨로지 노드 체크박스 목록)
 */
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Calendar, Database, Info } from 'lucide-react';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';

/** 온톨로지 노드 목록 (추후 Synapse API에서 로드) */
const AVAILABLE_NODES = [
  {
    id: 'node_costs',
    name: '원가 데이터',
    layer: 'Measure',
    fields: ['cost_index', 'material_cost', 'labor_cost'],
  },
  {
    id: 'node_production',
    name: '생산 데이터',
    layer: 'Process',
    fields: ['throughput', 'cycle_time', 'batch_size'],
  },
  {
    id: 'node_quality',
    name: '품질 지표',
    layer: 'Measure',
    fields: ['defect_rate', 'rework_rate', 'scrap_rate'],
  },
  {
    id: 'node_kpi',
    name: 'OEE KPI',
    layer: 'KPI',
    fields: ['oee_score', 'availability', 'performance'],
  },
  {
    id: 'node_maintenance',
    name: '정비 데이터',
    layer: 'Resource',
    fields: ['mtbf', 'mttr', 'maintenance_cost'],
  },
  {
    id: 'node_inventory',
    name: '재고 데이터',
    layer: 'Resource',
    fields: ['raw_material_stock', 'wip_level', 'finished_goods'],
  },
];

/** 온톨로지 레이어별 색상 */
const LAYER_COLORS: Record<string, string> = {
  KPI: 'bg-red-500/10 text-red-400 border-red-500/30',
  Measure: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  Process: 'bg-green-500/10 text-green-400 border-green-500/30',
  Resource: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
};

export function StepDataSelect() {
  const {
    dateRange,
    setDateRange,
    selectedNodes,
    toggleNode,
    setSelectedNodes,
  } = useWhatIfWizardStore();

  /** 전체 선택/해제 */
  const allSelected = selectedNodes.length === AVAILABLE_NODES.length;
  const handleSelectAll = () => {
    if (allSelected) {
      setSelectedNodes([]);
    } else {
      setSelectedNodes(AVAILABLE_NODES.map((n) => n.id));
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Database className="w-5 h-5 text-primary" />
          데이터 소스 및 기간 선택
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          인과 분석에 사용할 데이터 범위와 온톨로지 노드를 선택합니다.
        </p>
      </div>

      {/* 날짜 범위 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            분석 기간
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="space-y-1 flex-1">
              <Label htmlFor="date-from">시작일</Label>
              <Input
                id="date-from"
                type="date"
                value={dateRange.from}
                onChange={(e) =>
                  setDateRange({ ...dateRange, from: e.target.value })
                }
              />
            </div>
            <span className="text-muted-foreground mt-6">~</span>
            <div className="space-y-1 flex-1">
              <Label htmlFor="date-to">종료일</Label>
              <Input
                id="date-to"
                type="date"
                value={dateRange.to}
                onChange={(e) =>
                  setDateRange({ ...dateRange, to: e.target.value })
                }
              />
            </div>
          </div>
          <div className="flex items-start gap-2 mt-3 p-2 rounded-md bg-muted/50">
            <Info className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
            <p className="text-xs text-muted-foreground">
              기간을 지정하지 않으면 전체 데이터를 사용합니다.
              데이터가 많을수록 인과 분석의 정확도가 높아집니다.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 노드 선택 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">
              분석 대상 노드{' '}
              <span className="text-muted-foreground font-normal">
                ({selectedNodes.length}/{AVAILABLE_NODES.length} 선택)
              </span>
            </CardTitle>
            <button
              type="button"
              onClick={handleSelectAll}
              className="text-xs text-primary hover:underline"
            >
              {allSelected ? '전체 해제' : '전체 선택'}
            </button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {AVAILABLE_NODES.map((node) => {
              const isSelected = selectedNodes.includes(node.id);
              return (
                <label
                  key={node.id}
                  className={`
                    flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all
                    ${
                      isSelected
                        ? 'border-primary/40 bg-primary/5'
                        : 'border-border hover:border-primary/20 hover:bg-muted/30'
                    }
                  `}
                >
                  <Checkbox
                    checked={isSelected}
                    onCheckedChange={() => toggleNode(node.id)}
                    className="mt-0.5"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium">{node.name}</span>
                      <Badge
                        variant="outline"
                        className={`text-[10px] px-1.5 py-0 ${
                          LAYER_COLORS[node.layer] ?? ''
                        }`}
                      >
                        {node.layer}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {node.fields.join(', ')}
                    </p>
                  </div>
                </label>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
