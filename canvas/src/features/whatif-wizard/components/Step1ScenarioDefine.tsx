/**
 * Step 1: 시나리오 정의
 *
 * - 시나리오 이름 입력
 * - 시나리오 설명(선택)
 * - 시뮬레이션 모드 선택 (DAG vs Event Fork)
 */
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText, Lightbulb } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { SimulationModeToggle } from './SimulationModeToggle';

export function Step1ScenarioDefine() {
  const { t } = useTranslation();
  const {
    scenarioName,
    setScenarioName,
    scenarioDescription,
    setScenarioDescription,
    simulationMode,
    setSimulationMode,
  } = useWhatIfWizardStore();

  return (
    <div className="space-y-6 max-w-2xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary" />
          {t('whatifWizard.step1.title', '시나리오 정의')}
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          {t(
            'whatifWizard.step1.description',
            'What-if 분석의 기본 정보와 시뮬레이션 방식을 설정합니다.',
          )}
        </p>
      </div>

      {/* 기본 정보 카드 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">
            {t('whatifWizard.step1.basicInfo', '기본 정보')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 시나리오 이름 */}
          <div className="space-y-2">
            <Label htmlFor="ww-scenario-name">
              {t('whatifWizard.step1.nameLabel', '시나리오 이름')}{' '}
              <span className="text-destructive">*</span>
            </Label>
            <Input
              id="ww-scenario-name"
              placeholder={t(
                'whatifWizard.step1.namePlaceholder',
                '예: 원가 20% 상승 시 OEE 영향 분석',
              )}
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              maxLength={100}
              aria-required="true"
            />
          </div>

          {/* 설명 */}
          <div className="space-y-2">
            <Label htmlFor="ww-scenario-desc">
              {t('whatifWizard.step1.descLabel', '설명 (선택)')}
            </Label>
            <Textarea
              id="ww-scenario-desc"
              placeholder={t(
                'whatifWizard.step1.descPlaceholder',
                '이 시나리오의 목적과 배경을 설명하세요...',
              )}
              value={scenarioDescription}
              onChange={(e) => setScenarioDescription(e.target.value)}
              rows={3}
              maxLength={500}
            />
            <p className="text-xs text-muted-foreground text-right">
              {scenarioDescription.length}/500
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 시뮬레이션 모드 선택 카드 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Lightbulb className="w-4 h-4" />
            {t('whatifWizard.step1.modeTitle', '시뮬레이션 모드')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <SimulationModeToggle mode={simulationMode} onChange={setSimulationMode} />

          {/* 모드별 팁 */}
          <div className="mt-4 p-3 rounded-lg bg-muted/30 border border-border">
            <p className="text-xs text-muted-foreground">
              {simulationMode === 'dag' ? (
                <>
                  <strong className="text-foreground">DAG 모드 선택됨:</strong> Step 3에서
                  인과 관계를 자동 발견하고, 학습된 모델 체인을 통해 개입 효과가 연쇄
                  전파되는 과정을 시뮬레이션합니다.
                </>
              ) : (
                <>
                  <strong className="text-foreground">Event Fork 모드 선택됨:</strong>{' '}
                  실제 이벤트 스트림을 분기하여 개입 값을 적용합니다. Step 3(인과 발견)은
                  자동으로 건너뛸 수 있습니다.
                </>
              )}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
