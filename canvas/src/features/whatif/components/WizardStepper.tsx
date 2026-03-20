/**
 * WizardStepper — 5단계 진행 표시 바
 *
 * 각 단계의 상태(완료/현재/미진행)를 시각적으로 표시하고
 * 클릭으로 단계 전환을 지원한다.
 */
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WizardStep } from '../types/wizard';
import { WIZARD_STEPS, WIZARD_STEP_META } from '../types/wizard';

interface WizardStepperProps {
  /** 현재 활성 단계 */
  currentStep: WizardStep;
  /** 완료된 단계 목록 */
  completedSteps: WizardStep[];
  /** 단계 클릭 핸들러 */
  onStepClick: (step: WizardStep) => void;
}

export function WizardStepper({
  currentStep,
  completedSteps,
  onStepClick,
}: WizardStepperProps) {
  const currentIdx = WIZARD_STEPS.indexOf(currentStep);

  return (
    <nav aria-label="위자드 단계" className="w-full">
      <ol className="flex items-center gap-2">
        {WIZARD_STEPS.map((step, idx) => {
          const meta = WIZARD_STEP_META[step];
          const isActive = step === currentStep;
          const isCompleted = completedSteps.includes(step);
          // 현재 단계 이전이거나 완료된 단계는 클릭 가능
          const isClickable = idx <= currentIdx || isCompleted;

          return (
            <li key={step} className="flex-1 flex items-center">
              {/* 단계 버튼 */}
              <button
                type="button"
                onClick={() => isClickable && onStepClick(step)}
                disabled={!isClickable}
                aria-current={isActive ? 'step' : undefined}
                className={cn(
                  'flex items-center gap-2 w-full px-3 py-2 rounded-lg transition-all text-left',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isActive &&
                    'bg-primary/10 border border-primary/30 text-primary',
                  isCompleted &&
                    !isActive &&
                    'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/15',
                  !isActive &&
                    !isCompleted &&
                    'bg-muted/30 border border-transparent text-muted-foreground',
                  !isClickable && 'opacity-40 cursor-not-allowed',
                  isClickable && !isActive && 'cursor-pointer hover:bg-muted/50'
                )}
              >
                {/* 단계 번호 또는 완료 체크 */}
                <span
                  className={cn(
                    'flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold shrink-0',
                    isActive && 'bg-primary text-primary-foreground',
                    isCompleted && !isActive && 'bg-emerald-500 text-white',
                    !isActive && !isCompleted && 'bg-muted text-muted-foreground'
                  )}
                >
                  {isCompleted ? (
                    <Check className="w-3.5 h-3.5" />
                  ) : (
                    idx + 1
                  )}
                </span>

                {/* 라벨 */}
                <span className="text-xs font-medium truncate">
                  {meta.label}
                </span>
              </button>

              {/* 연결선 (마지막 항목 제외) */}
              {idx < WIZARD_STEPS.length - 1 && (
                <div
                  className={cn(
                    'w-6 h-px mx-1 shrink-0',
                    isCompleted ? 'bg-emerald-500/50' : 'bg-border'
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
