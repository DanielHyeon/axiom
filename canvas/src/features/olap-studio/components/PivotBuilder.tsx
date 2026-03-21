/**
 * PivotBuilder — 피벗 설정 영역.
 *
 * 행(Rows), 열(Columns), 측정값(Measures), 필터(Filters) 4개 드롭 영역으로 구성.
 * 각 영역에 필드 칩을 추가/제거할 수 있다.
 */
import { cn } from '@/lib/utils';
import { X, Rows3, Columns3, BarChart3, Filter } from 'lucide-react';
import type { PivotField, PivotMeasure, PivotFilter } from '../hooks/usePivot';

// ─── Props ────────────────────────────────────────────────

interface PivotBuilderProps {
  rows: PivotField[];
  columns: PivotField[];
  measures: PivotMeasure[];
  filters: PivotFilter[];
  onRemoveRow: (idx: number) => void;
  onRemoveColumn: (idx: number) => void;
  onRemoveMeasure: (idx: number) => void;
  onRemoveFilter: (idx: number) => void;
}

// ─── 메인 컴포넌트 ───────────────────────────────────────

export function PivotBuilder({
  rows,
  columns,
  measures,
  filters,
  onRemoveRow,
  onRemoveColumn,
  onRemoveMeasure,
  onRemoveFilter,
}: PivotBuilderProps) {
  return (
    <div className="grid grid-cols-2 gap-3 p-3">
      {/* 행 영역 */}
      <DropZone
        label="행 (Rows)"
        icon={<Rows3 className="h-3 w-3" />}
        color="blue"
        items={rows.map((r) => `${r.dimension}.${r.level}`)}
        onRemove={onRemoveRow}
      />

      {/* 열 영역 */}
      <DropZone
        label="열 (Columns)"
        icon={<Columns3 className="h-3 w-3" />}
        color="purple"
        items={columns.map((c) => `${c.dimension}.${c.level}`)}
        onRemove={onRemoveColumn}
      />

      {/* 측정값 영역 */}
      <DropZone
        label="측정값 (Measures)"
        icon={<BarChart3 className="h-3 w-3" />}
        color="emerald"
        items={measures.map((m) => `${m.aggregator}(${m.name})`)}
        onRemove={onRemoveMeasure}
      />

      {/* 필터 영역 */}
      <DropZone
        label="필터 (Filters)"
        icon={<Filter className="h-3 w-3" />}
        color="amber"
        items={filters.map(
          (f) =>
            `${f.dimension}.${f.level} ${f.operator} ${Array.isArray(f.value) ? f.value.join(',') : f.value}`,
        )}
        onRemove={onRemoveFilter}
      />
    </div>
  );
}

// ─── 드롭 영역 컴포넌트 ──────────────────────────────────

/** 색상별 스타일 매핑 */
const COLOR_MAP: Record<string, { bg: string; border: string; chip: string; text: string }> = {
  blue: {
    bg: 'bg-blue-50/50',
    border: 'border-blue-200',
    chip: 'bg-blue-100 text-blue-700',
    text: 'text-blue-400',
  },
  purple: {
    bg: 'bg-purple-50/50',
    border: 'border-purple-200',
    chip: 'bg-purple-100 text-purple-700',
    text: 'text-purple-400',
  },
  emerald: {
    bg: 'bg-emerald-50/50',
    border: 'border-emerald-200',
    chip: 'bg-emerald-100 text-emerald-700',
    text: 'text-emerald-400',
  },
  amber: {
    bg: 'bg-amber-50/50',
    border: 'border-amber-200',
    chip: 'bg-amber-100 text-amber-700',
    text: 'text-amber-400',
  },
};

interface DropZoneProps {
  label: string;
  icon: React.ReactNode;
  color: string;
  items: string[];
  onRemove: (idx: number) => void;
}

/** 개별 드롭 영역 — 필드 칩 목록과 빈 상태를 표시한다 */
function DropZone({ label, icon, color, items, onRemove }: DropZoneProps) {
  const c = COLOR_MAP[color] || COLOR_MAP.blue;

  return (
    <div className={cn('rounded-lg border p-3 min-h-[80px]', c.bg, c.border)}>
      {/* 영역 라벨 */}
      <div
        className={cn(
          'flex items-center gap-1.5 mb-2 text-[10px] font-[IBM_Plex_Mono] font-medium',
          c.text,
        )}
      >
        {icon}
        {label}
        {items.length > 0 && <span className="ml-auto opacity-60">{items.length}</span>}
      </div>

      {/* 빈 상태 또는 필드 칩 목록 */}
      {items.length === 0 ? (
        <p className="text-[10px] text-foreground/20 font-[IBM_Plex_Mono] text-center py-2">
          필드를 추가하세요
        </p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {items.map((item, idx) => (
            <span
              key={`${item}-${idx}`}
              className={cn(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-[IBM_Plex_Mono]',
                c.chip,
              )}
            >
              {item}
              <button
                type="button"
                onClick={() => onRemove(idx)}
                className="hover:opacity-60"
                aria-label={`${item} 제거`}
              >
                <X className="h-2.5 w-2.5" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
