/**
 * ConditionRow — GWT 규칙의 Given 조건 한 행 편집기
 *
 * 조건 타입(state/relation/expression), 계층, 필드, 연산자, 값을 편집한다.
 * 삭제 버튼으로 해당 조건을 제거할 수 있다.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type {
  GWTCondition,
  ConditionType,
  OntologyLayer,
  ComparisonOperator,
} from '../types/domainModeler.types';

// 온톨로지 계층 옵션 (레이어 이름은 고유명사이므로 번역 불필요)
const LAYER_OPTIONS: { value: OntologyLayer; label: string }[] = [
  { value: 'kpi', label: 'KPI' },
  { value: 'driver', label: 'Driver' },
  { value: 'measure', label: 'Measure' },
  { value: 'process', label: 'Process' },
  { value: 'resource', label: 'Resource' },
];

// 비교 연산자 옵션
const OPERATORS: { value: ComparisonOperator; label: string }[] = [
  { value: '==', label: '==' },
  { value: '!=', label: '!=' },
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '>=' },
  { value: '<=', label: '<=' },
];

interface ConditionRowProps {
  /** 조건 데이터 */
  condition: GWTCondition;
  /** 조건 변경 콜백 */
  onChange: (updated: GWTCondition) => void;
  /** 삭제 콜백 */
  onDelete: () => void;
  /** 읽기 전용 모드 */
  disabled?: boolean;
}

export const ConditionRow: React.FC<ConditionRowProps> = ({
  condition,
  onChange,
  onDelete,
  disabled = false,
}) => {
  const { t } = useTranslation();

  // 조건 타입 옵션 (번역 적용)
  const CONDITION_TYPES: { value: ConditionType; label: string }[] = [
    { value: 'state', label: t('domainModeler.conditionType.state') },
    { value: 'relation', label: t('domainModeler.conditionType.relation') },
    { value: 'expression', label: t('domainModeler.conditionType.expression') },
  ];

  /** 필드 하나를 업데이트하는 헬퍼 */
  const patch = (partial: Partial<GWTCondition>) => {
    onChange({ ...condition, ...partial });
  };

  return (
    <div
      className="flex items-center gap-2 rounded-md border border-border/50 bg-muted/30 p-2"
      role="group"
      aria-label={t('domainModeler.conditionAriaLabel', { field: condition.field || t('domainModeler.conditionNotSet') })}
    >
      {/* 조건 타입 */}
      <Select
        value={condition.type}
        onValueChange={(v) => patch({ type: v as ConditionType })}
        disabled={disabled}
      >
        <SelectTrigger className="w-24 h-8 text-xs">
          <SelectValue placeholder={t('domainModeler.typePlaceholder')} />
        </SelectTrigger>
        <SelectContent>
          {CONDITION_TYPES.map((ct) => (
            <SelectItem key={ct.value} value={ct.value}>
              {ct.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 대상 계층 */}
      <Select
        value={condition.layer}
        onValueChange={(v) => patch({ layer: v as OntologyLayer })}
        disabled={disabled}
      >
        <SelectTrigger className="w-28 h-8 text-xs">
          <SelectValue placeholder={t('domainModeler.layerPlaceholder')} />
        </SelectTrigger>
        <SelectContent>
          {LAYER_OPTIONS.map((lo) => (
            <SelectItem key={lo.value} value={lo.value}>
              {lo.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 필드명 */}
      <Input
        className="h-8 text-xs flex-1 min-w-[80px]"
        placeholder={t('domainModeler.fieldPlaceholder')}
        value={condition.field}
        onChange={(e) => patch({ field: e.target.value })}
        disabled={disabled}
        aria-label={t('domainModeler.fieldAriaLabel')}
      />

      {/* 연산자 */}
      <Select
        value={condition.operator}
        onValueChange={(v) => patch({ operator: v as ComparisonOperator })}
        disabled={disabled}
      >
        <SelectTrigger className="w-20 h-8 text-xs">
          <SelectValue placeholder="Op" />
        </SelectTrigger>
        <SelectContent>
          {OPERATORS.map((op) => (
            <SelectItem key={op.value} value={op.value}>
              {op.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 비교 값 */}
      <Input
        className="h-8 text-xs w-24"
        placeholder={t('domainModeler.valuePlaceholder')}
        value={condition.value}
        onChange={(e) => patch({ value: e.target.value })}
        disabled={disabled}
        aria-label={t('domainModeler.valueAriaLabel')}
      />

      {/* 삭제 버튼 */}
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0 text-destructive hover:text-destructive"
        onClick={onDelete}
        disabled={disabled}
        aria-label={t('domainModeler.deleteCondition')}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
};
