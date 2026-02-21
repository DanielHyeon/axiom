import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import { useOntologyMock } from '@/features/ontology/hooks/useOntologyMock';
import { Button } from '@/components/ui/button';
import { Network, ArrowRight } from 'lucide-react';
import { useMemo } from 'react';
import type { OntologyLayer } from '@/features/ontology/types/ontology';

const LAYER_LABELS: Record<OntologyLayer, string> = {
    kpi: 'KPI',
    measure: 'Measure',
    process: 'Process',
    resource: 'Resource'
};

interface NodeDetailProps {
    onFindPath: (targetId: string) => void;
}

export function NodeDetail({ onFindPath }: NodeDetailProps) {
    const { selectedNodeId } = useOntologyStore();
    const { graphData } = useOntologyMock(); // In a real app, you'd fetch specific node details

    const selectedNode = useMemo(() => {
        return graphData.nodes.find(n => n.id === selectedNodeId) || null;
    }, [graphData.nodes, selectedNodeId]);

    const connections = useMemo(() => {
        if (!selectedNodeId) return [];
        return graphData.links.filter(l => {
            const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
            const targetId = typeof l.target === 'object' ? l.target.id : l.target;
            return sourceId === selectedNodeId || targetId === selectedNodeId;
        }).map(l => {
            const source = typeof l.source === 'object' ? l.source : graphData.nodes.find(n => n.id === l.source);
            const target = typeof l.target === 'object' ? l.target : graphData.nodes.find(n => n.id === l.target);

            const isOutgoing = source?.id === selectedNodeId;
            const connectedNode = isOutgoing ? target : source;

            return {
                id: connectedNode?.id || '',
                label: connectedNode?.label || 'Unknown',
                relation: l.type,
                direction: isOutgoing ? 'out' : 'in'
            };
        });
    }, [graphData.links, graphData.nodes, selectedNodeId]);

    if (!selectedNode) {
        return (
            <div className="w-80 border-l border-neutral-800 bg-[#161616] p-6 flex flex-col items-center justify-center text-neutral-500">
                <Network size={32} className="mb-4 opacity-20" />
                <p className="text-sm">노드를 선택하면</p>
                <p className="text-sm">상세 정보가 표시됩니다.</p>
            </div>
        );
    }

    return (
        <div className="w-80 border-l border-neutral-800 bg-[#161616] flex flex-col h-full overflow-hidden">
            <div className="p-5 border-b border-neutral-800 bg-[#1a1a1a]">
                <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">
                    선택된 개체
                </div>
                <h2 className="text-lg font-bold text-neutral-100">{selectedNode.label}</h2>
                <div className="flex items-center gap-2 mt-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-neutral-800 text-neutral-300">
                        {LAYER_LABELS[selectedNode.layer]}
                    </span>
                    {selectedNode.type && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-neutral-800 text-neutral-300">
                            {selectedNode.type}
                        </span>
                    )}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-6">
                {/* Properties */}
                <div>
                    <h3 className="text-sm font-semibold text-neutral-300 mb-3 flex items-center">
                        속성
                    </h3>
                    <div className="space-y-2 bg-[#1a1a1a] rounded-md p-3 border border-neutral-800/50">
                        {Object.entries(selectedNode.properties).map(([key, value]) => (
                            <div key={key} className="flex justify-between text-sm">
                                <span className="text-neutral-500 capitalize">{key}:</span>
                                <span className="text-neutral-200">{value}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Connections */}
                <div>
                    <h3 className="text-sm font-semibold text-neutral-300 mb-3 flex items-center justify-between">
                        연결
                        <span className="text-xs bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-400">
                            {connections.length}
                        </span>
                    </h3>
                    <div className="space-y-1.5">
                        {connections.map((conn, idx) => (
                            <div key={idx} className="flex items-center gap-2 text-sm bg-[#1a1a1a] p-2 rounded border border-neutral-800/30 hover:border-neutral-700 transition-colors">
                                <span className="text-neutral-500 min-w-[30px] text-xs">
                                    {conn.direction === 'out' ? '→' : '←'}
                                </span>
                                <span className="flex-1 text-neutral-300 truncate" title={conn.label}>{conn.label}</span>
                                <span className="text-[10px] text-neutral-500 bg-neutral-900 px-1.5 py-0.5 border border-neutral-800 rounded">
                                    {conn.relation}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="p-4 border-t border-neutral-800 bg-[#1a1a1a] space-y-2">
                <Button
                    variant="outline"
                    className="w-full text-xs justify-between"
                    onClick={() => onFindPath(selectedNode.id)}
                >
                    이 노드로 경로 탐색 <ArrowRight size={14} className="ml-2 opacity-50" />
                </Button>
            </div>
        </div>
    );
}
