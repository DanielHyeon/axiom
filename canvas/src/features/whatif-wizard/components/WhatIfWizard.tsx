/**
 * WhatIfWizard — 5단계 위자드 메인 컨테이너
 *
 * DAG Propagation + Event Fork 두 모드를 지원하는
 * 통합 What-if 시뮬레이션 위자드.
 *
 * 5단계:
 *  1. 시나리오 정의 (이름, 설명, 모드)
 *  2. 데이터 선택 (온톨로지 노드)
 *  3. 인과 관계 발견
 *  4. 개입 설정 (파라미터 변경)
 *  5. 결과 비교
 */
import { useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Check, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { WIZARD_STEP_META } from '../types/whatifWizard.types';
import type { WizardStepNumber } from '../types/whatifWizard.types';
import { Step1ScenarioDefine } from './Step1ScenarioDefine';
import { Step2DataSelect } from './Step2DataSelect';
import { Step3CausalDiscovery } from './Step3CausalDiscovery';
import { Step4Intervention } from './Step4Intervention';
import { Step5ResultCompare } from './Step5ResultCompare';

/** 위자드 단계 목록 */
const STEPS: WizardStepNumber[] = [1, 2, 3, 4, 5];

export function WhatIfWizard() {
  const { t } = useTranslation();
  const store = useWhatIfWizardStore();
  const { currentStep, goToStep, nextStep, prevStep, canProceed, resetWizard } = store;

  const isFirst = currentStep === 1;
  const isLast = currentStep === 5;

  // 완료된 단계 판정
  const completedSteps = useMemo((): Set<WizardStepNumber> => {
    const state = useWhatIfWizardStore.getState();
    const completed = new Set<WizardStepNumber>();

    // Step 1: 시나리오 이름 입력됨
    if (state.scenarioName.trim()) completed.add(1);
    // Step 2: 노드 선택됨
    if (state.selectedNodeIds.length > 0) completed.add(2);
    // Step 3: 인과관계 발견됨 또는 Event Fork 모드(자동 스킵)
    if (state.causalRelations.length > 0 || state.simulationMode === 'event-fork') {
      completed.add(3);
    }
    // Step 4: 개입 설정됨
    if (state.interventions.length > 0) completed.add(4);
    // Step 5: 결과 있음
    if (state.forkResults.length > 0) completed.add(5);

    return completed;
  }, [
    store.scenarioName,
    store.selectedNodeIds,
    store.causalRelations,
    store.simulationMode,
    store.interventions,
    store.forkResults,
  ]);

  // 스텝 클릭 핸들러
  const handleStepClick = useCallback(
    (step: WizardStepNumber) => {
      goToStep(step);
    },
    [goToStep],
  );

  // 현재 단계 컴포넌트 렌더링
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return <Step1ScenarioDefine />;
      case 2:
        return <Step2DataSelect />;
      case 3:
        return <Step3CausalDiscovery />;
      case 4:
        return <Step4Intervention />;
      case 5:
        return <Step5ResultCompare />;
      default:
        return null;
    }
  };

  const stepMeta = WIZARD_STEP_META[currentStep];

  return (
    <div className="flex flex-col h-full bg-background text-foreground">
      {/* 상단: 스텝 인디케이터 */}
      <div className="shrink-0 border-b border-border bg-card px-6 py-3">
        <nav aria-label="위자드 단계" className="w-full">
          <ol className="flex items-center gap-2">
            {STEPS.map((step, idx) => {
              const meta = WIZARD_STEP_META[step];
              const isActive = step === currentStep;
              const isCompleted = completedSteps.has(step);
              const isClickable = step <= currentStep || isCompleted;

              return (
                <li key={step} className="flex-1 flex items-center">
                  <button
                    type="button"
                    onClick={() => isClickable && handleStepClick(step)}
                    disabled={!isClickable}
                    aria-current={isActive ? 'step' : undefined}
                    className={cn(
                      'flex items-center gap-2 w-full px-3 py-2 rounded-lg transition-all text-left',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      isActive && 'bg-primary/10 border border-primary/30 text-primary',
                      isCompleted &&
                        !isActive &&
                        'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/15',
                      !isActive &&
                        !isCompleted &&
                        'bg-muted/30 border border-transparent text-muted-foreground',
                      !isClickable && 'opacity-40 cursor-not-allowed',
                      isClickable && !isActive && 'cursor-pointer hover:bg-muted/50',
                    )}
                  >
                    {/* 단계 번호 또는 완료 체크 */}
                    <span
                      className={cn(
                        'flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold shrink-0',
                        isActive && 'bg-primary text-primary-foreground',
                        isCompleted && !isActive && 'bg-emerald-500 text-white',
                        !isActive && !isCompleted && 'bg-muted text-muted-foreground',
                      )}
                    >
                      {isCompleted ? <Check className="w-3.5 h-3.5" /> : step}
                    </span>

                    {/* 라벨 */}
                    <span className="text-xs font-medium truncate">{meta.label}</span>
                  </button>

                  {/* 연결선 */}
                  {idx < STEPS.length - 1 && (
                    <div
                      className={cn(
                        'w-6 h-px mx-1 shrink-0',
                        isCompleted ? 'bg-emerald-500/50' : 'bg-border',
                      )}
                    />
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      </div>

      {/* 단계 설명 헤더 */}
      <div className="shrink-0 px-6 py-3 border-b border-border bg-muted/20">
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Step {currentStep} / {STEPS.length} &mdash; {stepMeta.description}
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetWizard}
            className="h-7 text-xs text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="w-3 h-3 mr-1" />
            {t('whatifWizard.reset', '초기화')}
          </Button>
        </div>
      </div>

      {/* 메인 콘텐츠 영역 */}
      <div className="flex-1 overflow-y-auto px-6 py-6">{renderStepContent()}</div>

      {/* 하단: 네비게이션 버튼 */}
      <div className="shrink-0 border-t border-border bg-card px-6 py-3">
        <div className="flex items-center justify-between">
          {/* 이전 버튼 */}
          <Button
            variant="outline"
            size="sm"
            onClick={prevStep}
            disabled={isFirst}
            className="h-9"
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            {t('whatifWizard.prev', '이전')}
          </Button>

          {/* 진행 표시 */}
          <span className="text-xs text-muted-foreground">
            {currentStep} / {STEPS.length}
          </span>

          {/* 다음 버튼 */}
          {!isLast ? (
            <Button
              size="sm"
              onClick={nextStep}
              disabled={!canProceed()}
              className="h-9"
            >
              {t('whatifWizard.next', '다음')}
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          ) : (
            <div className="w-[72px]" />
          )}
        </div>
      </div>
    </div>
  );
}
