/**
 * LineageFilter — 깊이 슬라이더, 방향 토글, 노드 타입 필터
 * 리니지 그래프 상단 도구 모음에 인라인으로 배치
 */

import { ArrowLeft, ArrowRight, ArrowLeftRight } from 'lucide-react';
import { useLineageStore } from '../store/useLineageStore';
import {
  LINEAGE_NODE_STYLES,
  type LineageDirection,
  type LineageNodeType,
} from '../types/lineage';

/** 방향 옵션 정의 */
const DIRECTION_OPTIONS: { value: LineageDirection; label: string; Icon: React.FC<{ className?: string }> }[] = [
  { value: 'upstream', label: 'Upstream', Icon: ArrowLeft },
  { value: 'both', label: 'Both', Icon: ArrowLeftRight },
  { value: 'downstream', label: 'Downstream', Icon: ArrowRight },
];

/** 필터 대상 노드 타입 목록 */
const NODE_TYPE_LIST: LineageNodeType[] = [
  'source',
  'table',
  'column',
  'view',
  'transform',
  'report',
];

export function LineageFilter() {
  const { filters, setDirection, setDepth, toggleNodeType } = useLineageStore();

  return (
    <div className="flex flex-wrap items-center gap-4" role="toolbar" aria-label="리니지 필터">
      {/* ── 방향 토글 ── */}
      <fieldset className="flex items-center gap-1">
        <legend className="sr-only">탐색 방향</legend>
        {DIRECTION_OPTIONS.map(({ value, label, Icon }) => {
          const active = filters.direction === value;
          return (
            <button
              key={value}
              onClick={() => setDirection(value)}
              title={label}
              aria-pressed={active}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{label}</span>
            </button>
          );
        })}
      </fieldset>

      {/* ── 깊이 슬라이더 ── */}
      <div className="flex items-center gap-2">
        <label
          htmlFor="lineage-depth"
          className="text-xs font-medium text-muted-foreground whitespace-nowrap"
        >
          깊이: {filters.depth}
        </label>
        <input
          id="lineage-depth"
          type="range"
          min={1}
          max={5}
          step={1}
          value={filters.depth}
          onChange={(e) => setDepth(Number(e.target.value))}
          className="h-1.5 w-24 appearance-none rounded-full bg-muted accent-primary cursor-pointer"
          aria-label="리니지 탐색 깊이"
        />
      </div>

      {/* ── 노드 타입 토글 ── */}
      <fieldset className="flex items-center gap-1">
        <legend className="sr-only">노드 타입 필터</legend>
        {NODE_TYPE_LIST.map((type) => {
          const style = LINEAGE_NODE_STYLES[type];
          const active = filters.nodeTypes.has(type);
          return (
            <button
              key={type}
              onClick={() => toggleNodeType(type)}
              aria-pressed={active}
              title={style.label}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-semibold uppercase transition-colors border ${
                active
                  ? 'text-white border-transparent'
                  : 'text-muted-foreground border-border bg-muted/30 opacity-50 hover:opacity-80'
              }`}
              style={active ? { background: style.color, borderColor: style.borderColor } : undefined}
            >
              <span
                className="inline-block h-2 w-2 rounded-sm"
                style={{ background: style.color }}
              />
              {style.label}
            </button>
          );
        })}
      </fieldset>
    </div>
  );
}
