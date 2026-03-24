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
import { useTranslation } from 'react-i18next';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';

/** 미리 정의된 케이스/스키마 목록 (추후 API에서 로드) */
const AVAILABLE_CASES = [
  { id: 'demo_manufacturing', nameKey: 'whatifExt.demoScenarios.manufacturing' },
  { id: 'demo_logistics', nameKey: 'whatifExt.demoScenarios.logistics' },
  { id: 'demo_quality', nameKey: 'whatifExt.demoScenarios.quality' },
];

/** 대상 KPI 목록 (추후 Synapse 온톨로지에서 로드) */
const AVAILABLE_KPIS = [
  { id: 'oee', nameKey: 'whatifExt.demoKpis.oee' },
  { id: 'throughput_rate', nameKey: 'whatifExt.demoKpis.throughputRate' },
  { id: 'defect_rate', nameKey: 'whatifExt.demoKpis.defectRate' },
  { id: 'downtime', nameKey: 'whatifExt.demoKpis.downtime' },
  { id: 'mtbf', nameKey: 'whatifExt.demoKpis.mtbf' },
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

  const { t } = useTranslation();

  return (
    <div className="space-y-6 max-w-2xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary" />
          {t('whatifExt.scenarioDefine.heading')}
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          {t('whatifExt.scenarioDefine.headingDesc')}
        </p>
      </div>

      {/* 시나리오 이름 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">{t('whatifExt.scenarioDefine.basicInfo')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="scenario-name">
              {t('whatifWizard.step1.nameLabel')} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="scenario-name"
              placeholder={t('whatifExt.scenarioDefine.namePlaceholder')}
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              maxLength={100}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="scenario-desc">{t('whatifExt.scenarioDefine.descOpt')}</Label>
            <Textarea
              id="scenario-desc"
              placeholder={t('whatifExt.scenarioDefine.descPlaceholder')}
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
            {t('whatifExt.scenarioDefine.analysisTarget')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 케이스(스키마) 선택 */}
          <div className="space-y-2">
            <Label htmlFor="case-select">
              {t('whatifExt.scenarioDefine.caseLabel')} <span className="text-destructive">*</span>
            </Label>
            <Select value={caseId} onValueChange={setCaseId}>
              <SelectTrigger id="case-select">
                <SelectValue placeholder={t('whatifExt.scenarioDefine.selectCase')} />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_CASES.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {t(c.nameKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t('whatifExt.scenarioDefine.caseHint')}
            </p>
          </div>

          {/* 대상 KPI 선택 */}
          <div className="space-y-2">
            <Label htmlFor="kpi-select">{t('whatifExt.scenarioDefine.kpiLabel')}</Label>
            <Select value={targetKpiId} onValueChange={setTargetKpiId}>
              <SelectTrigger id="kpi-select">
                <SelectValue placeholder={t('whatifExt.scenarioDefine.selectKpi')} />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_KPIS.map((k) => (
                  <SelectItem key={k.id} value={k.id}>
                    {t(k.nameKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t('whatifExt.scenarioDefine.kpiHint')}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
