/**
 * SimulationModeToggle — DAG / Event Fork 모드 전환 토글
 *
 * 두 가지 시뮬레이션 모드를 시각적으로 구분하고
 * 각 모드의 특징을 설명하는 UI를 제공한다.
 */
import { cn } from '@/lib/utils';
import { GitBranch, Network } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { SimulationMode } from '../types/whatifWizard.types';

interface SimulationModeToggleProps {
  /** 현재 선택된 모드 */
  mode: SimulationMode;
  /** 모드 변경 콜백 */
  onChange: (mode: SimulationMode) => void;
}

/** 모드별 아이콘 정보 */
const MODE_ICON: Record<SimulationMode, typeof Network> = {
  dag: Network,
  'event-fork': GitBranch,
};

/** 모드별 i18n 키 */
const MODE_KEYS: Record<SimulationMode, { labelKey: string; descKey: string }> = {
  dag: { labelKey: 'whatifWizard.mode.dagPropagation', descKey: 'whatifWizard.mode.dagDesc' },
  'event-fork': { labelKey: 'whatifWizard.mode.eventFork', descKey: 'whatifWizard.mode.eventDesc' },
};

export function SimulationModeToggle({ mode, onChange }: SimulationModeToggleProps) {
  const { t } = useTranslation();
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {(Object.keys(MODE_KEYS) as SimulationMode[]).map(
          (modeKey) => {
            const isSelected = mode === modeKey;
            const Icon = MODE_ICON[modeKey];
            const keys = MODE_KEYS[modeKey];

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
                    {t(keys.labelKey)}
                  </span>
                </div>

                {/* 설명 */}
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {t(keys.descKey)}
                </p>
              </button>
            );
          },
        )}
      </div>
    </div>
  );
}
