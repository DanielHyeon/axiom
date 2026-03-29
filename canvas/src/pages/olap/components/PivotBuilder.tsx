/**
 * PivotBuilder — 피벗 드롭 존 행 + 실행 버튼
 *
 * .pen 디자인 사양:
 * - Drop Zones row: 3개 동일 너비 컬럼, 12px gap
 *   ROWS zone / COLUMNS zone / VALUES zone
 * - 하단에 실행 버튼 행 (필요 시)
 */
import { usePivotConfig } from '@/features/olap/store/usePivotConfig';
import { DroppableZone } from './DroppableZone';
import { Button } from '@/components/ui/button';
import { ArrowLeftRight, Play, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface PivotBuilderProps {
  onRunQuery: () => void;
  isQuerying: boolean;
}

export function PivotBuilder({ onRunQuery, isQuerying }: PivotBuilderProps) {
  const { t } = useTranslation();
  const { rows, columns, measures, removeFieldFromZone, setRows, setColumns } = usePivotConfig();

  // 행↔열 교환
  const handleSwap = () => {
    const tempRows = [...rows];
    setRows(columns);
    setColumns(tempRows);
  };

  // 최소 조건: 측정값 1개 + (행 또는 열 1개)
  const hasRequiredFields = measures.length > 0 && (rows.length > 0 || columns.length > 0);

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* 3개 드롭 존 — 동일 너비, 12px gap */}
      <div className="grid grid-cols-3 gap-3">
        <DroppableZone
          id="rows"
          title="ROWS"
          items={rows}
          onRemove={(id) => removeFieldFromZone('rows', id)}
        />
        <DroppableZone
          id="columns"
          title="COLUMNS"
          items={columns}
          onRemove={(id) => removeFieldFromZone('columns', id)}
        />
        <DroppableZone
          id="measures"
          title="VALUES"
          items={measures}
          onRemove={(id) => removeFieldFromZone('measures', id)}
        />
      </div>

      {/* 액션 버튼 행 */}
      <div className="flex items-center justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleSwap}
          disabled={isQuerying || (rows.length === 0 && columns.length === 0)}
          className="h-8 text-xs text-text-secondary border-border"
        >
          <ArrowLeftRight size={12} className="mr-1" />
          {t('olapPage.swapRowCol')}
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={onRunQuery}
          disabled={!hasRequiredFields || isQuerying}
          className="h-8 text-xs bg-primary hover:bg-primary/90 text-primary-foreground border-0"
        >
          {isQuerying ? (
            <Loader2 size={12} className="mr-1 animate-spin" />
          ) : (
            <Play size={12} className="mr-1" />
          )}
          {t('olapPage.runAnalysis')}
        </Button>
      </div>
    </div>
  );
}
