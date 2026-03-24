/**
 * 적중 정책 선택기 — FIRST / COLLECT / PRIORITY.
 * KG-1: DMN 결정 테이블의 규칙 매칭 방식을 선택한다.
 */

import { useTranslation } from 'react-i18next';
import type { HitPolicy } from '../types/dmn';

interface HitPolicySelectorProps {
  value: HitPolicy;
  onChange: (policy: HitPolicy) => void;
  disabled?: boolean;
}

const POLICY_KEYS: { value: HitPolicy; label: string; descKey: string }[] = [
  { value: 'FIRST', label: 'First', descKey: 'dmn.hitPolicy.first' },
  { value: 'COLLECT', label: 'Collect', descKey: 'dmn.hitPolicy.collect' },
  { value: 'PRIORITY', label: 'Priority', descKey: 'dmn.hitPolicy.priority' },
];

export function HitPolicySelector({ value, onChange, disabled }: HitPolicySelectorProps) {
  const { t } = useTranslation();
  return (
    <div className="flex gap-1" role="radiogroup" aria-label={t('dmn.hitPolicy.ariaLabel')}>
      {POLICY_KEYS.map((p) => (
        <button
          key={p.value}
          type="button"
          role="radio"
          aria-checked={value === p.value}
          title={t(p.descKey)}
          disabled={disabled}
          onClick={() => onChange(p.value)}
          className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
            value === p.value
              ? 'bg-primary text-primary-foreground border-primary'
              : 'bg-card text-muted-foreground border-border hover:bg-muted'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
