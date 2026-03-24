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
          {t('whatifWizard.step1.title')}
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          {t(
            'whatifWizard.step1.description',
            t('whatifWizardF.step1Description'),
          )}
        </p>
      </div>

      {/* 기본 정보 카드 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">
            {t('whatifWizard.step1.basicInfo')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 시나리오 이름 */}
          <div className="space-y-2">
            <Label htmlFor="ww-scenario-name">
              {t('whatifWizard.step1.nameLabel')}{' '}
              <span className="text-destructive">*</span>
            </Label>
            <Input
              id="ww-scenario-name"
              placeholder={t(
                'whatifWizard.step1.namePlaceholder',
                t('whatifWizardF.step1NamePlaceholder'),
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
              {t('whatifWizard.step1.descLabel')}
            </Label>
            <Textarea
              id="ww-scenario-desc"
              placeholder={t(
                'whatifWizard.step1.descPlaceholder',
                t('whatifWizardF.step1DescPlaceholder'),
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
            {t('whatifWizard.step1.modeTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <SimulationModeToggle mode={simulationMode} onChange={setSimulationMode} />

          {/* 모드별 팁 */}
          <div className="mt-4 p-3 rounded-lg bg-muted/30 border border-border">
            <p className="text-xs text-muted-foreground">
              {simulationMode === 'dag' ? (
                <>
                  {t('whatifWizardF.step1EventForkNote')}
                  {t('whatifWizardF.mddeea804')}
                  {t('whatifWizardF.mdac84299')}
                </>
              ) : (
                <>
                  <strong className="text-foreground">{t('whatifWizardF.msgf4027fc0')}</strong>{' '}
                  {t('whatifWizardF.mbd747488')}
                  {t('whatifWizardF.m4cc18511')}
                </>
              )}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
