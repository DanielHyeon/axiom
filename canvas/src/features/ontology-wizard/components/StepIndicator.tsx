/**
 * StepIndicator — 수평 단계 표시기
 * 번호가 매겨진 원형과 연결선으로 위자드 진행 상태를 시각화
 */
import { Check } from 'lucide-react';
import type { WizardStep } from '../types/wizard';

/** 단계 정의 */
const STEPS: Array<{ key: WizardStep; label: string }> = [
  { key: 'INPUT', label: '입력' },
  { key: 'GENERATING', label: '생성 중' },
  { key: 'REVIEW', label: '검토' },
  { key: 'COMPLETE', label: '완료' },
];

/** 단계 키 → 순서 번호 (1부터 시작) */
function stepIndex(step: WizardStep): number {
  return STEPS.findIndex((s) => s.key === step);
}

interface StepIndicatorProps {
  currentStep: WizardStep;
}

export function StepIndicator({ currentStep }: StepIndicatorProps) {
  const currentIdx = stepIndex(currentStep);

  return (
    <div className="flex items-center justify-center w-full px-4 py-2">
      {STEPS.map((s, i) => {
        const isCompleted = i < currentIdx;
        const isActive = i === currentIdx;

        return (
          <div key={s.key} className="flex items-center">
            {/* 원형 번호 */}
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={`
                  w-9 h-9 rounded-full flex items-center justify-center
                  text-sm font-semibold transition-colors duration-300
                  ${isCompleted
                    ? 'bg-green-500 text-primary-foreground'
                    : isActive
                      ? 'bg-primary text-primary-foreground ring-2 ring-primary/30'
                      : 'bg-muted text-muted-foreground'
                  }
                `}
              >
                {isCompleted ? <Check size={16} /> : i + 1}
              </div>
              <span
                className={`text-xs whitespace-nowrap ${
                  isActive
                    ? 'text-foreground font-medium'
                    : isCompleted
                      ? 'text-green-600 font-medium'
                      : 'text-muted-foreground'
                }`}
              >
                {s.label}
              </span>
            </div>

            {/* 연결선 (마지막 요소 제외) */}
            {i < STEPS.length - 1 && (
              <div
                className={`
                  w-16 h-0.5 mx-2 transition-colors duration-300
                  ${i < currentIdx ? 'bg-green-500' : 'bg-muted'}
                `}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
