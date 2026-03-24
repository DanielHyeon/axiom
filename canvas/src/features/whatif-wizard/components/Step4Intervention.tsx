/**
 * Step 4: 개입(Intervention) 파라미터 설정
 *
 * - 선택된 노드별로 필드 이름 + 값 슬라이더/인풋 제공
 * - 개입 설명 입력
 * - 개입 추가/삭제 버튼
 * - 베이스라인 값 표시
 */
import { useState, useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, Trash2, SlidersHorizontal, ArrowRightLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import type { InterventionSpec } from '../types/whatifWizard.types';

/**
 * 노드별 사용 가능한 필드 목록
 * 실제로는 Synapse/Weaver에서 동적으로 로드하지만, 폴백 데이터 제공
 */
const NODE_FIELDS: Record<string, Array<{ field: string; label: string; baseline: number }>> = {
  kpi_oee: [
    { field: 'oee_score', label: 'OEE 점수', baseline: 78.5 },
  ],
  kpi_throughput: [
    { field: 'throughput', label: '생산량 (개/시간)', baseline: 850 },
  ],
  kpi_defect: [
    { field: 'defect_rate', label: '불량률 (%)', baseline: 3.2 },
  ],
  kpi_downtime: [
    { field: 'downtime_hours', label: '중단 시간 (시간)', baseline: 4.5 },
  ],
  msr_availability: [
    { field: 'availability_pct', label: '가용률 (%)', baseline: 92 },
  ],
  msr_performance: [
    { field: 'performance_pct', label: '성능 효율 (%)', baseline: 88 },
  ],
  msr_quality: [
    { field: 'quality_pct', label: '품질률 (%)', baseline: 97 },
  ],
  msr_cycle_time: [
    { field: 'cycle_time_sec', label: '사이클 타임 (초)', baseline: 12.3 },
  ],
  msr_mtbf: [
    { field: 'mtbf_hours', label: 'MTBF (시간)', baseline: 720 },
  ],
  prc_assembly: [
    { field: 'assembly_speed', label: '조립 속도', baseline: 100 },
    { field: 'worker_count', label: '작업자 수', baseline: 5 },
  ],
  prc_inspection: [
    { field: 'inspection_rate', label: '검사 비율 (%)', baseline: 100 },
  ],
  prc_packaging: [
    { field: 'packaging_speed', label: '포장 속도', baseline: 120 },
  ],
  prc_maintenance: [
    { field: 'maintenance_interval', label: '정비 주기 (일)', baseline: 30 },
  ],
  rsc_machine_a: [
    { field: 'machine_load', label: '설비 부하 (%)', baseline: 75 },
    { field: 'machine_age', label: '설비 연식 (년)', baseline: 5 },
  ],
  rsc_robot_01: [
    { field: 'robot_speed', label: '로봇 속도 (%)', baseline: 100 },
  ],
  rsc_operator: [
    { field: 'operator_count', label: '운영 인력 수', baseline: 10 },
    { field: 'skill_level', label: '숙련도 (1-10)', baseline: 7 },
  ],
  rsc_material: [
    { field: 'material_cost', label: '원자재 비용 (만원)', baseline: 45.5 },
    { field: 'material_quality', label: '원자재 품질 (1-10)', baseline: 8 },
  ],
};

/** 기본 필드 (매핑이 없는 노드용) */
const DEFAULT_FIELDS = [
  { field: 'value', label: '값', baseline: 100 },
];

export function Step4Intervention() {
  const { t } = useTranslation();
  const {
    selectedNodes,
    interventions,
    addIntervention,
    removeIntervention,
    updateIntervention,
  } = useWhatIfWizardStore();

  // 새 개입 추가 폼 상태
  const [newNodeId, setNewNodeId] = useState('');
  const [newField, setNewField] = useState('');
  const [newValue, setNewValue] = useState(0);
  const [newDescription, setNewDescription] = useState('');

  // 선택된 노드의 필드 목록
  const getNodeFields = useCallback((nodeId: string) => {
    return NODE_FIELDS[nodeId] ?? DEFAULT_FIELDS;
  }, []);

  // 새 개입 추가 핸들러
  const handleAddIntervention = useCallback(() => {
    if (!newNodeId || !newField) return;

    const node = selectedNodes.find((n) => n.id === newNodeId);
    const fields = getNodeFields(newNodeId);
    const fieldInfo = fields.find((f) => f.field === newField);

    if (!node || !fieldInfo) return;

    const spec: InterventionSpec = {
      nodeId: newNodeId,
      nodeName: node.name,
      field: newField,
      value: newValue || fieldInfo.baseline,
      baselineValue: fieldInfo.baseline,
      description: newDescription || `${node.name} - ${fieldInfo.label} 변경`,
    };

    addIntervention(spec);

    // 폼 초기화
    setNewNodeId('');
    setNewField('');
    setNewValue(0);
    setNewDescription('');
  }, [newNodeId, newField, newValue, newDescription, selectedNodes, getNodeFields, addIntervention]);

  // 노드 선택 시 첫 번째 필드 자동 선택
  const handleNodeChange = useCallback(
    (nodeId: string) => {
      setNewNodeId(nodeId);
      const fields = getNodeFields(nodeId);
      if (fields.length > 0) {
        setNewField(fields[0].field);
        setNewValue(fields[0].baseline);
      }
    },
    [getNodeFields],
  );

  // 필드 변경 시 베이스라인 값 설정
  const handleFieldChange = useCallback(
    (field: string) => {
      setNewField(field);
      const fields = getNodeFields(newNodeId);
      const fi = fields.find((f) => f.field === field);
      if (fi) setNewValue(fi.baseline);
    },
    [newNodeId, getNodeFields],
  );

  return (
    <div className="space-y-6 max-w-3xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <SlidersHorizontal className="w-5 h-5 text-primary" />
          {t('whatifWizard.step4.title', '개입 설정')}
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          {t(
            'whatifWizard.step4.description',
            '시뮬레이션에서 변경할 파라미터 값을 설정합니다.',
          )}
        </p>
      </div>

      {/* 기존 개입 목록 */}
      {interventions.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">설정된 개입</CardTitle>
              <Badge variant="secondary" className="text-xs">
                {interventions.length}개
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {interventions.map((iv, idx) => {
              const fields = getNodeFields(iv.nodeId);
              const fieldInfo = fields.find((f) => f.field === iv.field);
              const baseline = fieldInfo?.baseline ?? iv.baselineValue;
              const delta = iv.value - baseline;
              const pctChange = baseline !== 0 ? (delta / Math.abs(baseline)) * 100 : 0;
              // 슬라이더 범위: 베이스라인의 0~200%
              const sliderMin = 0;
              const sliderMax = baseline === 0 ? 200 : baseline * 2;
              const step = baseline === 0 ? 1 : baseline * 0.01;

              return (
                <div
                  key={`${iv.nodeId}-${iv.field}-${idx}`}
                  className="p-3 rounded-lg border border-border bg-muted/20 space-y-3"
                >
                  {/* 헤더: 노드 이름 + 필드 + 삭제 */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{iv.nodeName}</span>
                      <ArrowRightLeft className="w-3 h-3 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">{iv.field}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeIntervention(idx)}
                      aria-label="개입 삭제"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>

                  {/* 값 슬라이더 + 입력 */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">
                        {fieldInfo?.label ?? iv.field}
                      </Label>
                      <div className="flex items-center gap-2">
                        <Input
                          type="number"
                          step="any"
                          value={iv.value}
                          onChange={(e) =>
                            updateIntervention(idx, {
                              value: parseFloat(e.target.value) || 0,
                            })
                          }
                          className="w-24 h-7 text-xs text-right font-mono"
                        />
                        {/* 변화량 표시 */}
                        <Badge
                          variant="outline"
                          className={cn(
                            'text-[10px] font-mono',
                            delta > 0
                              ? 'text-emerald-400 border-emerald-500/30'
                              : delta < 0
                                ? 'text-red-400 border-red-500/30'
                                : 'text-muted-foreground',
                          )}
                        >
                          {delta > 0 ? '+' : ''}
                          {pctChange.toFixed(1)}%
                        </Badge>
                      </div>
                    </div>
                    <Slider
                      value={[iv.value]}
                      min={sliderMin}
                      max={sliderMax}
                      step={step}
                      onValueChange={([v]) =>
                        updateIntervention(idx, { value: v })
                      }
                      className="w-full"
                    />
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                      <span>베이스라인: {baseline.toFixed(1)}</span>
                      <span>변경값: {iv.value.toFixed(1)}</span>
                    </div>
                  </div>

                  {/* 설명 */}
                  <Input
                    placeholder="개입 설명..."
                    value={iv.description}
                    onChange={(e) =>
                      updateIntervention(idx, { description: e.target.value })
                    }
                    className="h-7 text-xs"
                  />
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* 새 개입 추가 카드 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Plus className="w-4 h-4" />
            개입 추가
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 노드 선택 */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label className="text-xs">대상 노드</Label>
              <Select value={newNodeId} onValueChange={handleNodeChange}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="노드 선택" />
                </SelectTrigger>
                <SelectContent>
                  {selectedNodes.map((node) => (
                    <SelectItem key={node.id} value={node.id} className="text-xs">
                      {node.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 필드 선택 */}
            <div className="space-y-2">
              <Label className="text-xs">대상 필드</Label>
              <Select
                value={newField}
                onValueChange={handleFieldChange}
                disabled={!newNodeId}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="필드 선택" />
                </SelectTrigger>
                <SelectContent>
                  {newNodeId &&
                    getNodeFields(newNodeId).map((f) => (
                      <SelectItem key={f.field} value={f.field} className="text-xs">
                        {f.label} (현재: {f.baseline})
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* 값 입력 */}
          {newNodeId && newField && (
            <div className="space-y-2">
              <Label className="text-xs">변경 값</Label>
              <Input
                type="number"
                step="any"
                value={newValue}
                onChange={(e) => setNewValue(parseFloat(e.target.value) || 0)}
                className="h-8 text-xs"
              />
            </div>
          )}

          {/* 설명 입력 */}
          <div className="space-y-2">
            <Label className="text-xs">설명 (선택)</Label>
            <Input
              placeholder="이 개입의 목적을 설명하세요..."
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              className="h-8 text-xs"
            />
          </div>

          {/* 추가 버튼 */}
          <Button
            onClick={handleAddIntervention}
            disabled={!newNodeId || !newField}
            variant="outline"
            className="w-full"
            size="sm"
          >
            <Plus className="w-4 h-4 mr-2" />
            개입 추가
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
