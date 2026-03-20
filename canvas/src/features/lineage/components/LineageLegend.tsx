/**
 * LineageLegend — 노드 타입별 범례 패널
 * 그래프 우측 상단에 고정 위치로 렌더링된다.
 */

import { LINEAGE_NODE_STYLES, type LineageNodeType } from '../types/lineage';

const LEGEND_ITEMS: { type: LineageNodeType; label: string }[] = [
  { type: 'source', label: '소스' },
  { type: 'table', label: '테이블' },
  { type: 'column', label: '컬럼' },
  { type: 'view', label: '뷰' },
  { type: 'transform', label: '변환' },
  { type: 'report', label: '리포트' },
];

export function LineageLegend() {
  return (
    <div
      className="absolute top-4 right-4 z-10 rounded-xl border border-border bg-card p-3.5 shadow-lg min-w-[150px]"
      role="region"
      aria-label="리니지 범례"
    >
      {/* 제목 */}
      <p className="mb-2.5 text-xs font-bold text-foreground tracking-wide">
        Data Lineage
      </p>

      {/* 노드 타입 목록 */}
      <ul className="flex flex-col gap-1.5 mb-2.5">
        {LEGEND_ITEMS.map(({ type, label }) => {
          const style = LINEAGE_NODE_STYLES[type];
          return (
            <li key={type} className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span
                className="inline-block w-3 h-3 rounded"
                style={{ background: style.color }}
              />
              <span>{label}</span>
            </li>
          );
        })}
      </ul>

      {/* 데이터 흐름 표시 */}
      <div className="flex items-center gap-2 pt-2 border-t border-border text-[11px] text-muted-foreground">
        <span className="inline-block w-6 h-0.5 bg-muted-foreground relative">
          <span className="absolute -right-1.5 -top-[5px] text-xs">&rarr;</span>
        </span>
        <span>데이터 흐름</span>
      </div>
    </div>
  );
}
