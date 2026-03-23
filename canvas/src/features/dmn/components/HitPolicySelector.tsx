/**
 * 적중 정책 선택기 — FIRST / COLLECT / PRIORITY.
 * KG-1: DMN 결정 테이블의 규칙 매칭 방식을 선택한다.
 */

import type { HitPolicy } from '../types/dmn';

interface HitPolicySelectorProps {
  value: HitPolicy;
  onChange: (policy: HitPolicy) => void;
  disabled?: boolean;
}

const POLICIES: { value: HitPolicy; label: string; description: string }[] = [
  { value: 'FIRST', label: 'First', description: '첫 번째 매칭 규칙만 적용' },
  { value: 'COLLECT', label: 'Collect', description: '모든 매칭 규칙의 결과를 수집' },
  { value: 'PRIORITY', label: 'Priority', description: '우선순위가 가장 높은 규칙 적용' },
];

export function HitPolicySelector({ value, onChange, disabled }: HitPolicySelectorProps) {
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="적중 정책">
      {POLICIES.map((p) => (
        <button
          key={p.value}
          type="button"
          role="radio"
          aria-checked={value === p.value}
          title={p.description}
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
