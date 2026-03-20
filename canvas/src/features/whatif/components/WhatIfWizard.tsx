/**
 * WhatIfWizard — 5단계 위자드 메인 컨테이너
 *
 * KAIR WhatIfPanel(6단계)을 참고하여
 * Axiom 패턴(React + shadcn/ui + Tailwind)으로 재구현.
 *
 * 5단계:
 *  1. 시나리오 정의
 *  2. 데이터 소스/기간 선택
 *  3. 인과 관계 발견
 *  4. 모델 학습
 *  5. 시뮬레이션 실행
 */
import { useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { WIZARD_STEPS, WIZARD_STEP_META } from '../types/wizard';
import type { WizardStep } from '../types/wizard';
import { WizardStepper } from './WizardStepper';
import { StepScenarioDefine } from './StepScenarioDefine';
import { StepDataSelect } from './StepDataSelect';
import { StepEdgeDiscovery } from './StepEdgeDiscovery';
import { StepTrainModels } from './StepTrainModels';
import { StepSimulation } from './StepSimulation';

export function WhatIfWizard() {
  const store = useWhatIfWizardStore();
  const { currentStep, goToStep, nextStep, prevStep, canProceed, resetWizard } = store;

  const currentIdx = WIZARD_STEPS.indexOf(currentStep);
  const isFirst = currentIdx === 0;
  const isLast = currentIdx === WIZARD_STEPS.length - 1;

  // 완료된 단계 계산 (현재 단계 이전 + 유효성 충족 단계)
  const completedSteps = useMemo((): WizardStep[] => {
    const completed: WizardStep[] = [];
    const state = useWhatIfWizardStore.getState();

    // Step 1 완료: 시나리오 이름 + 케이스 ID
    if (state.scenarioName.trim() && state.caseId.trim()) {
      completed.push('scenario');
    }
    // Step 2 완료: 노드 선택
    if (state.selectedNodes.length > 0) {
      completed.push('data');
    }
    // Step 3 완료: 엣지 발견 + 선택
    if (state.discoveredEdges.some((e) => e.selected)) {
      completed.push('edges');
    }
    // Step 4 완료: 학습 완료
    if (state.trainedModels.some((m) => m.status === 'trained')) {
      completed.push('train');
    }
    // Step 5는 마지막이므로 완료 조건 없음
    if (state.simulationResults.length > 0) {
      completed.push('simulate');
    }

    return completed;
  }, [
    // eslint-disable-next-line react-hooks/exhaustive-deps
    store.scenarioName,
    store.caseId,
    store.selectedNodes,
    store.discoveredEdges,
    store.trainedModels,
    store.simulationResults,
  ]);

  // 단계 전환 핸들러
  const handleStepClick = useCallback(
    (step: WizardStep) => {
      goToStep(step);
    },
    [goToStep]
  );

  // 현재 단계 메타데이터
  const stepMeta = WIZARD_STEP_META[currentStep];

  // 현재 단계 컴포넌트 렌더링
  const renderStepContent = () => {
    switch (currentStep) {
      case 'scenario':
        return <StepScenarioDefine />;
      case 'data':
        return <StepDataSelect />;
      case 'edges':
        return <StepEdgeDiscovery />;
      case 'train':
        return <StepTrainModels />;
      case 'simulate':
        return <StepSimulation />;
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full bg-background text-foreground">
      {/* 상단: 위자드 스테퍼 */}
      <div className="shrink-0 border-b border-border bg-card px-6 py-3">
        <WizardStepper
          currentStep={currentStep}
          completedSteps={completedSteps}
          onStepClick={handleStepClick}
        />
      </div>

      {/* 단계 설명 헤더 */}
      <div className="shrink-0 px-6 py-3 border-b border-border bg-muted/20">
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Step {currentIdx + 1} / {WIZARD_STEPS.length} &mdash;{' '}
            {stepMeta.description}
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetWizard}
            className="h-7 text-xs text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="w-3 h-3 mr-1" />
            초기화
          </Button>
        </div>
      </div>

      {/* 메인 콘텐츠 영역 */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {renderStepContent()}
      </div>

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
            이전
          </Button>

          {/* 진행 표시 */}
          <span className="text-xs text-muted-foreground">
            {currentIdx + 1} / {WIZARD_STEPS.length}
          </span>

          {/* 다음 버튼 */}
          {!isLast ? (
            <Button
              size="sm"
              onClick={nextStep}
              disabled={!canProceed()}
              className="h-9"
            >
              다음
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          ) : (
            <div className="w-[72px]" /> // 마지막 단계는 다음 버튼 없음
          )}
        </div>
      </div>
    </div>
  );
}
