// src/pages/olap/components/DimensionPalette.tsx

import { usePivotConfig } from '@/features/olap/store/usePivotConfig';
import type { CubeDefinition } from '@/features/olap/types/olap';
import { DraggableItem } from './DraggableItem';
import { Database } from 'lucide-react';

interface DimensionPaletteProps {
    cube: CubeDefinition | null;
}

export function DimensionPalette({ cube }: DimensionPaletteProps) {
    const { rows, columns, measures, filters } = usePivotConfig();

    if (!cube) {
        return (
            <div className="w-64 border-r border-neutral-800 bg-[#161616] p-4 flex flex-col items-center justify-center text-neutral-500">
                <Database size={32} className="mb-2 opacity-20" />
                <p className="text-sm">큐브를 선택하세요</p>
            </div>
        );
    }

    // Determine which fields are already in use
    const inUseDimensions = new Set([
        ...rows.map(r => r.id),
        ...columns.map(c => c.id),
        ...filters.map(f => f.dimensionId)
    ]);

    const inUseMeasures = new Set(measures.map(m => m.id));

    return (
        <div className="w-64 border-r border-neutral-800 bg-[#161616] flex flex-col">
            <div className="p-4 border-b border-neutral-800 bg-[#1a1a1a]">
                <h3 className="font-medium text-sm text-neutral-200">{cube.name}</h3>
                <p className="text-xs text-neutral-500 mt-1">{cube.description}</p>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                <div>
                    <h4 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3 flex items-center justify-between">
                        차원 (Dimensions)
                        <span className="text-neutral-600 font-normal">{cube.dimensions.length}</span>
                    </h4>
                    <div className="space-y-1">
                        {cube.dimensions.map(dim => (
                            <DraggableItem
                                key={dim.id}
                                item={dim}
                                type="dimension"
                                disabled={inUseDimensions.has(dim.id)}
                            />
                        ))}
                    </div>
                </div>

                <div>
                    <h4 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3 flex items-center justify-between">
                        측정값 (Measures)
                        <span className="text-neutral-600 font-normal">{cube.measures.length}</span>
                    </h4>
                    <div className="space-y-1">
                        {cube.measures.map(meas => (
                            <DraggableItem
                                key={meas.id}
                                item={meas}
                                type="measure"
                                disabled={inUseMeasures.has(meas.id)}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
