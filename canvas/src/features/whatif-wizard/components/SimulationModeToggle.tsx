/**
 * SimulationModeToggle — DAG / Event Fork 모드 전환 토글
 *
 * 두 가지 시뮬레이션 모드를 시각적으로 구분하고
 * 각 모드의 특징을 설명하는 UI를 제공한다.
 */
import { cn } from '@/lib/utils';
import { GitBranch, Network } from 'lucide-react';
import type { SimulationMode } from '../types/whatifWizard.types';

interface SimulationModeToggleProps {
  /** 현재 선택된 모드 */
  mode: SimulationMode;
  /** 모드 변경 콜백 */
  onChange: (mode: SimulationMode) => void;
}

/** 모드별 설명 및 아이콘 정보 */
const MODE_INFO: Record<
  SimulationMode,
  { label: string; description: string; icon: typeof Network }
> = {
  dag: {
    label: 'DAG 전파',
    description:
      '인과 DAG 그래프를 따라 개입 효과가 전파되는 과정을 시뮬레이션합니다. ' +
      '학습된 예측 모델을 사용하여 연쇄 영향을 계산합니다.',
    icon: Network,
  },
  'event-fork': {
    label: 'Event Fork',
    description:
      '실제 이벤트 스트림을 복제하여 분기(fork)한 뒤 개입 값을 적용합니다. ' +
      '타임라인 기반으로 KPI 변화를 추적합니다.',
    icon: GitBranch,
  },
};

export function SimulationModeToggle({ mode, onChange }: SimulationModeToggleProps) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {(Object.entries(MODE_INFO) as [SimulationMode, (typeof MODE_INFO)[SimulationMode]][]).map(
          ([modeKey, info]) => {
            const isSelected = mode === modeKey;
            const Icon = info.icon;

            return (
              <button
                key={modeKey}
                type="button"
                onClick={() => onChange(modeKey)}
                aria-pressed={isSelected}
                className={cn(
                  'flex flex-col items-start gap-2 p-4 rounded-lg border-2 transition-all text-left',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isSelected
                    ? 'border-primary bg-primary/5 shadow-sm'
                    : 'border-border bg-card hover:border-muted-foreground/30 hover:bg-muted/30',
                )}
              >
                {/* 아이콘 + 라벨 */}
                <div className="flex items-center gap-2">
                  <Icon
                    className={cn(
                      'w-5 h-5',
                      isSelected ? 'text-primary' : 'text-muted-foreground',
                    )}
                  />
                  <span
                    className={cn(
                      'text-sm font-semibold',
                      isSelected ? 'text-primary' : 'text-foreground',
                    )}
                  >
                    {info.label}
                  </span>
                </div>

                {/* 설명 */}
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {info.description}
                </p>
              </button>
            );
          },
        )}
      </div>
    </div>
  );
}
