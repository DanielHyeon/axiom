/**
 * Step 1: 시나리오 정의
 *
 * - 시나리오 이름 및 설명 입력
 * - 케이스(스키마) 선택
 * - 대상 KPI 선택 (온톨로지에서)
 */
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText, Target } from 'lucide-react';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';

/** 미리 정의된 케이스/스키마 목록 (추후 API에서 로드) */
const AVAILABLE_CASES = [
  { id: 'demo_manufacturing', name: '제조업 OEE 분석' },
  { id: 'demo_logistics', name: '물류 최적화 시나리오' },
  { id: 'demo_quality', name: '품질 관리 시나리오' },
];

/** 대상 KPI 목록 (추후 Synapse 온톨로지에서 로드) */
const AVAILABLE_KPIS = [
  { id: 'oee', name: 'OEE (Overall Equipment Effectiveness)' },
  { id: 'throughput_rate', name: 'Throughput Rate (생산량)' },
  { id: 'defect_rate', name: 'Defect Rate (불량률)' },
  { id: 'downtime', name: 'Downtime (가동 중단 시간)' },
  { id: 'mtbf', name: 'MTBF (평균 고장 간격)' },
];

export function StepScenarioDefine() {
  const {
    scenarioName,
    setScenarioName,
    description,
    setDescription,
    caseId,
    setCaseId,
    targetKpiId,
    setTargetKpiId,
  } = useWhatIfWizardStore();

  return (
    <div className="space-y-6 max-w-2xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary" />
          시나리오 정의
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          What-if 분석의 기본 정보를 설정합니다. 시나리오 이름과 분석 대상 KPI를 선택하세요.
        </p>
      </div>

      {/* 시나리오 이름 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">기본 정보</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="scenario-name">
              시나리오 이름 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="scenario-name"
              placeholder="예: 원가 상승 시 OEE 영향 분석"
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              maxLength={100}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="scenario-desc">설명 (선택)</Label>
            <Textarea
              id="scenario-desc"
              placeholder="이 시나리오의 목적과 배경을 설명하세요..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              maxLength={500}
            />
            <p className="text-xs text-muted-foreground text-right">
              {description.length}/500
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 케이스 및 KPI 선택 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Target className="w-4 h-4" />
            분석 대상
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 케이스(스키마) 선택 */}
          <div className="space-y-2">
            <Label htmlFor="case-select">
              케이스 (데이터 스키마) <span className="text-destructive">*</span>
            </Label>
            <Select value={caseId} onValueChange={setCaseId}>
              <SelectTrigger id="case-select">
                <SelectValue placeholder="분석할 케이스를 선택하세요" />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_CASES.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              온톨로지에 등록된 데이터 스키마 기준으로 분석합니다.
            </p>
          </div>

          {/* 대상 KPI 선택 */}
          <div className="space-y-2">
            <Label htmlFor="kpi-select">대상 KPI (선택)</Label>
            <Select value={targetKpiId} onValueChange={setTargetKpiId}>
              <SelectTrigger id="kpi-select">
                <SelectValue placeholder="분석 대상 KPI를 선택하세요" />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_KPIS.map((k) => (
                  <SelectItem key={k.id} value={k.id}>
                    {k.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              특정 KPI를 지정하면 해당 KPI와 관련된 변수만 인과 분석에 포함됩니다.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
