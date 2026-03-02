import { Checkbox } from '@/components/ui/checkbox';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import type { OntologyLayer } from '@/features/ontology/types/ontology';

const LAYER_INFO: { id: OntologyLayer; label: string; color: string }[] = [
 { id: 'kpi', label: 'KPI', color: 'bg-destructive' },
 { id: 'measure', label: 'Measure', color: 'bg-warning' },
 { id: 'process', label: 'Process', color: 'bg-primary' },
 { id: 'resource', label: 'Resource', color: 'bg-success' }
];

export function LayerFilter() {
 const { filters, toggleLayer } = useOntologyStore();

 return (
 <div className="flex gap-4 items-center bg-[#F5F5F5] p-2 rounded border border-[#E5E5E5]">
 <span className="text-[11px] text-foreground/60 font-[IBM_Plex_Mono] mr-2">계층:</span>
 {LAYER_INFO.map(layer => (
 <div key={layer.id} className="flex items-center space-x-2">
 <Checkbox
 id={`layer-${layer.id}`}
 checked={filters.layers.has(layer.id)}
 onCheckedChange={() => toggleLayer(layer.id)}
 />
 <label
 htmlFor={`layer-${layer.id}`}
 className="text-[13px] cursor-pointer flex items-center gap-1.5 text-[#5E5E5E] font-[Sora]"
 >
 <span className={`w-2.5 h-2.5 rounded-full ${layer.color}`} />
 {layer.label}
 </label>
 </div>
 ))}
 </div>
 );
}
