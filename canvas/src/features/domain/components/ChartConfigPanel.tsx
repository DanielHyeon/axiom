/**
 * ChartConfigPanel — 시각화 설정 패널
 *
 * ObjectType의 차트 유형(bar, line, pie, map)과 축 매핑을 설정한다.
 * KAIR ChartConfigTab.vue를 React + shadcn/ui로 재구현.
 */

import React from 'react';
import { BarChart3, LineChart, PieChart, Map } from 'lucide-react';
// Label은 기본 HTML label로 대체
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { ChartConfig, ChartType, ObjectTypeField } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface ChartConfigPanelProps {
  /** 현재 차트 설정 */
  config: ChartConfig;
  /** 변경 콜백 */
  onChange: (config: ChartConfig) => void;
  /** 사용 가능한 필드 목록 */
  fields: ObjectTypeField[];
  /** 읽기 전용 */
  readOnly?: boolean;
}

// ──────────────────────────────────────
// 차트 유형 옵션
// ──────────────────────────────────────

const CHART_OPTIONS: { value: ChartType; label: string; icon: React.ReactNode; description: string }[] = [
  { value: 'none', label: '없음', icon: null, description: '차트 없음' },
  { value: 'bar', label: '바 차트', icon: <BarChart3 className="h-4 w-4" />, description: '카테고리별 값 비교' },
  { value: 'line', label: '라인 차트', icon: <LineChart className="h-4 w-4" />, description: '시계열 데이터' },
  { value: 'pie', label: '파이 차트', icon: <PieChart className="h-4 w-4" />, description: '비율/구성' },
  { value: 'map', label: '지도', icon: <Map className="h-4 w-4" />, description: '위치 기반' },
];

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const ChartConfigPanel: React.FC<ChartConfigPanelProps> = ({
  config,
  onChange,
  fields,
  readOnly = false,
}) => {
  const update = (patch: Partial<ChartConfig>) => onChange({ ...config, ...patch });

  // 숫자형 필드만 필터 (y축 / value 후보)
  const numericFields = fields.filter((f) =>
    ['integer', 'float', 'number', 'decimal', 'numeric', 'double'].some((t) =>
      f.dataType.toLowerCase().includes(t),
    ),
  );

  // 문자형 필드 (x축 / label 후보)
  const textFields = fields.filter(
    (f) => !numericFields.find((nf) => nf.id === f.id),
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-primary" />
          차트 설정
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 차트 유형 선택 */}
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">차트 유형</label>
          <div className="grid grid-cols-5 gap-1.5">
            {CHART_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => !readOnly && update({ chartType: opt.value })}
                disabled={readOnly}
                className={cn(
                  'flex flex-col items-center gap-1 p-2 rounded-md border text-xs transition-colors',
                  config.chartType === opt.value
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-muted/50',
                )}
              >
                {opt.icon ?? <span className="h-4 w-4 flex items-center justify-center text-xs">-</span>}
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 축 매핑 (차트가 'none'이 아닐 때) */}
        {config.chartType !== 'none' && (
          <>
            {/* bar / line: X축 + Y축 */}
            {(config.chartType === 'bar' || config.chartType === 'line') && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">X축 (카테고리)</label>
                  <Select
                    value={config.xAxis ?? ''}
                    onValueChange={(v) => update({ xAxis: v })}
                    disabled={readOnly}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue placeholder="필드 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {fields.map((f) => (
                        <SelectItem key={f.id} value={f.name} className="text-xs">
                          {f.displayName || f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">Y축 (값)</label>
                  <Select
                    value={config.yAxis ?? ''}
                    onValueChange={(v) => update({ yAxis: v })}
                    disabled={readOnly}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue placeholder="필드 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {numericFields.map((f) => (
                        <SelectItem key={f.id} value={f.name} className="text-xs">
                          {f.displayName || f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {/* pie: label + value */}
            {config.chartType === 'pie' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">라벨 필드</label>
                  <Select
                    value={config.labelField ?? ''}
                    onValueChange={(v) => update({ labelField: v })}
                    disabled={readOnly}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue placeholder="필드 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {textFields.map((f) => (
                        <SelectItem key={f.id} value={f.name} className="text-xs">
                          {f.displayName || f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">값 필드</label>
                  <Select
                    value={config.valueField ?? ''}
                    onValueChange={(v) => update({ valueField: v })}
                    disabled={readOnly}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue placeholder="필드 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {numericFields.map((f) => (
                        <SelectItem key={f.id} value={f.name} className="text-xs">
                          {f.displayName || f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};
