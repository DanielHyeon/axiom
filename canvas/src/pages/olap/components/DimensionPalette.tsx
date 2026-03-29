/**
 * DimensionPalette — OLAP 피벗 좌측 차원/측정값 팔레트
 *
 * .pen 디자인 사양:
 * - 220px 너비, 오른쪽 border, 16px 패딩, 12px gap
 * - "Dimensions" 제목: Sora 12px semibold
 * - 드래그 가능한 칩: 32px 높이, 흰색 bg, 6px radius, border
 *   아이콘(파란색 12px) + 텍스트 Geist 12px
 * - "Measures" 제목: Sora 12px semibold
 * - 측정값 칩: 같은 스타일, 녹색 아이콘(hash)
 */
import { usePivotConfig } from '@/features/olap/store/usePivotConfig';
import type { CubeDefinition } from '@/features/olap/types/olap';
import { DraggableItem } from './DraggableItem';
import { Database } from 'lucide-react';

interface DimensionPaletteProps {
  cube: CubeDefinition | null;
}

/** 차원에 사용할 아이콘 이름 매핑 (디자인의 calendar, map-pin, box 패턴) */
const DIMENSION_ICONS: Record<string, string> = {
  date: 'calendar',
  time: 'calendar',
  region: 'map-pin',
  location: 'map-pin',
  geography: 'map-pin',
  product: 'box',
  category: 'box',
};

/** 차원 이름으로 아이콘 결정 */
export function getDimensionIcon(name: string): string {
  const lower = name.toLowerCase();
  for (const [key, icon] of Object.entries(DIMENSION_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return 'box'; // 기본 아이콘
}

export function DimensionPalette({ cube }: DimensionPaletteProps) {
  const { rows, columns, measures: usedMeasures, filters } = usePivotConfig();

  // 큐브 미선택 시 빈 상태
  if (!cube) {
    return (
      <div className="flex flex-col items-center justify-center w-[220px] p-4 border-r border-border bg-card">
        <Database size={32} className="mb-2 text-text-placeholder" />
        <p className="text-xs text-text-placeholder">큐브를 선택하세요</p>
      </div>
    );
  }

  // 이미 사용 중인 차원/측정값
  const inUseDimensions = new Set([
    ...rows.map((r) => r.id),
    ...columns.map((c) => c.id),
    ...filters.map((f) => f.dimensionId),
  ]);
  const inUseMeasures = new Set(usedMeasures.map((m) => m.id));

  return (
    <div className="flex flex-col w-[220px] p-4 gap-3 border-r border-border bg-card overflow-y-auto shrink-0">
      {/* 차원 섹션 제목 */}
      <h4 className="font-heading text-xs font-semibold text-foreground">
        Dimensions
      </h4>

      {cube.dimensions
        .filter((dim) => !inUseDimensions.has(dim.id))
        .map((dim) => (
          <DraggableItem key={dim.id} item={dim} type="dimension" />
        ))}

      {/* 측정값 섹션 제목 */}
      <h4 className="font-heading text-xs font-semibold text-foreground mt-2">
        Measures
      </h4>

      {cube.measures
        .filter((m) => !inUseMeasures.has(m.id))
        .map((meas) => (
          <DraggableItem key={meas.id} item={meas} type="measure" />
        ))}
    </div>
  );
}
