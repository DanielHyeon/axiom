/**
 * OntologyWizard — 3단계 위자드 메인 컨테이너
 * KAIR OntologyWizard.vue를 이식
 * Step 1: DB 스키마 선택 (WizardStepSchema)
 * Step 2: 레이어 매핑 (WizardStepMapping)
 * Step 3: 검토 + 생성 (WizardStepReview)
 *
 * 모달로 표시되며, OntologyPage의 "위자드" 버튼으로 열립니다.
 */
import { X, Check } from 'lucide-react';
import { useOntologyWizard } from '../hooks/useOntologyWizard';
import { useOntologyWizardStore } from '../store/useOntologyWizardStore';
import { WizardStepSchema } from './WizardStepSchema';
import { WizardStepMapping } from './WizardStepMapping';
import { WizardStepReview } from './WizardStepReview';

// 단계 번호 계산
function stepNumber(step: string): number {
  if (step === 'schema') return 1;
  if (step === 'mapping') return 2;
  return 3;
}

const STEP_LABELS = ['스키마 선택', '레이어 매핑', '검토 + 생성'];

export function OntologyWizard() {
  const { isOpen, closeWizard } = useOntologyWizardStore();
  const wizard = useOntologyWizard();

  if (!isOpen) return null;

  const currentStepNum = stepNumber(wizard.step);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={closeWizard}
    >
      <div
        className="w-full max-w-3xl max-h-[90vh] bg-background border border-border rounded-xl shadow-2xl flex flex-col animate-in fade-in zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">온톨로지 위자드</h2>
          <button
            type="button"
            onClick={() => { wizard.reset(); closeWizard(); }}
            className="p-1.5 rounded hover:bg-muted text-muted-foreground"
          >
            <X size={18} />
          </button>
        </div>

        {/* 진행 표시줄 */}
        <div className="px-6 pt-4">
          <div className="flex items-center justify-between mb-3">
            {STEP_LABELS.map((label, i) => {
              const num = i + 1;
              const isActive = num === currentStepNum;
              const isCompleted = num < currentStepNum;
              return (
                <div key={label} className="flex flex-col items-center flex-1 gap-1.5">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                      isCompleted
                        ? 'bg-green-500 text-white'
                        : isActive
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {isCompleted ? <Check size={14} /> : num}
                  </div>
                  <span
                    className={`text-xs ${
                      isActive ? 'text-foreground font-medium' : isCompleted ? 'text-green-600' : 'text-muted-foreground'
                    }`}
                  >
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="h-1 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green-500 to-primary transition-all duration-500"
              style={{ width: `${((currentStepNum - 1) / 2) * 100}%` }}
            />
          </div>
        </div>

        {/* 컨텐츠 영역 */}
        <div className="flex-1 overflow-y-auto p-6">
          {wizard.step === 'schema' && <WizardStepSchema wizard={wizard} />}
          {wizard.step === 'mapping' && <WizardStepMapping wizard={wizard} />}
          {wizard.step === 'review' && <WizardStepReview wizard={wizard} onClose={closeWizard} />}
        </div>
      </div>
    </div>
  );
}
