// src/pages/olap/components/PivotBuilder.tsx

import { usePivotConfig } from '@/features/olap/store/usePivotConfig';
import { DroppableZone } from './DroppableZone';
import { Button } from '@/components/ui/button';
import { ArrowLeftRight, Play } from 'lucide-react';

interface PivotBuilderProps {
    onRunQuery: () => void;
    isQuerying: boolean;
}

export function PivotBuilder({ onRunQuery, isQuerying }: PivotBuilderProps) {
    const { rows, columns, measures, filters, removeFieldFromZone, setRows, setColumns } = usePivotConfig();

    const handleSwap = () => {
        const tempRows = [...rows];
        setRows(columns);
        setColumns(tempRows);
    };

    const hasRequiredFields = measures.length > 0 && (rows.length > 0 || columns.length > 0);

    return (
        <div className="bg-[#121212] flex-1 border-r border-neutral-800 p-6 flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-sm font-semibold text-neutral-200">피벗 빌더 (Drag & Drop)</h2>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={handleSwap} disabled={isQuerying}>
                        <ArrowLeftRight size={14} className="mr-1.5" /> 행↔열 전환
                    </Button>
                    <Button
                        size="sm"
                        onClick={onRunQuery}
                        disabled={!hasRequiredFields || isQuerying}
                        className="bg-indigo-600 hover:bg-indigo-700"
                    >
                        <Play size={14} className="mr-1.5" /> 분석 실행
                    </Button>
                </div>
            </div>

            <div className="bg-neutral-900 rounded-lg border border-neutral-800 p-4 space-y-2 relative">
                <DroppableZone id="rows" title="행 (Rows)" items={rows} onRemove={(id) => removeFieldFromZone('rows', id)} accepts="dimension" />
                <DroppableZone id="columns" title="열 (Columns)" items={columns} onRemove={(id) => removeFieldFromZone('columns', id)} accepts="dimension" />
                <DroppableZone id="measures" title="측정값 (Values)" items={measures} onRemove={(id) => removeFieldFromZone('measures', id)} accepts="measure" />
                <DroppableZone id="filters" title="필터 (Filters)" items={filters.map(f => ({ id: f.dimensionId, name: f.dimensionId, type: 'string' }))} onRemove={(id) => removeFieldFromZone('filters', id)} accepts="dimension" />

                {!hasRequiredFields && (
                    <div className="absolute -bottom-8 right-0 text-xs text-amber-500 font-medium">
                        측정값 1개 이상, 행 또는 열 1개 이상 배치하세요.
                    </div>
                )}
            </div>
        </div>
    );
}
