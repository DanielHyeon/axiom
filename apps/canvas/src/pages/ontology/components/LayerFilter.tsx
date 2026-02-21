import { Checkbox } from '@/components/ui/checkbox';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import type { OntologyLayer } from '@/features/ontology/types/ontology';

const LAYER_INFO: { id: OntologyLayer; label: string; color: string }[] = [
    { id: 'kpi', label: 'KPI', color: 'bg-red-500' },
    { id: 'measure', label: 'Measure', color: 'bg-amber-500' },
    { id: 'process', label: 'Process', color: 'bg-blue-500' },
    { id: 'resource', label: 'Resource', color: 'bg-emerald-500' }
];

export function LayerFilter() {
    const { filters, toggleLayer } = useOntologyStore();

    return (
        <div className="flex gap-4 items-center bg-[#1a1a1a] p-2 rounded-md border border-neutral-800">
            <span className="text-xs text-neutral-500 mr-2">계층:</span>
            {LAYER_INFO.map(layer => (
                <div key={layer.id} className="flex items-center space-x-2">
                    <Checkbox
                        id={`layer-${layer.id}`}
                        checked={filters.layers.has(layer.id)}
                        onCheckedChange={() => toggleLayer(layer.id)}
                    />
                    <label
                        htmlFor={`layer-${layer.id}`}
                        className="text-sm cursor-pointer flex items-center gap-1.5 text-neutral-300"
                    >
                        <span className={`w-2.5 h-2.5 rounded-full ${layer.color}`} />
                        {layer.label}
                    </label>
                </div>
            ))}
        </div>
    );
}
