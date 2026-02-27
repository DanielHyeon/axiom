import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import { useOntologyData } from '@/features/ontology/hooks/useOntologyData';
import { Button } from '@/components/ui/button';
import { Network, ArrowRight, Zap } from 'lucide-react';
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
    onImpactAnalysis: (nodeId: string) => void;
}

export function NodeDetail({ onFindPath, onImpactAnalysis }: NodeDetailProps) {
    const { selectedNodeId, caseId } = useOntologyStore();
    const { graphData } = useOntologyData(caseId);

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
            <div className="p-6 flex flex-col items-center justify-center text-[#999] h-full">
                <Network size={32} className="mb-4 opacity-20" />
                <p className="text-sm font-[IBM_Plex_Mono]">노드를 선택하면</p>
                <p className="text-sm font-[IBM_Plex_Mono]">상세 정보가 표시됩니다.</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between h-[52px] px-6 border-b border-[#E5E5E5] shrink-0">
                <span className="text-[13px] font-semibold text-black font-[Sora]">Node Details</span>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Node info */}
                <div className="space-y-2">
                    <h2 className="text-lg font-semibold text-black font-[Sora]">{selectedNode.label}</h2>
                    <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#F5F5F5] text-[#5E5E5E] font-[IBM_Plex_Mono]">
                            {LAYER_LABELS[selectedNode.layer]}
                        </span>
                        {selectedNode.type && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#F5F5F5] text-[#5E5E5E] font-[IBM_Plex_Mono]">
                                {selectedNode.type}
                            </span>
                        )}
                    </div>
                </div>

                {/* Properties */}
                <div>
                    <h3 className="text-[11px] font-semibold text-[#999] font-[IBM_Plex_Mono] uppercase tracking-wider mb-3">
                        속성
                    </h3>
                    <div className="space-y-2 bg-[#F5F5F5] rounded p-3">
                        {Object.entries(selectedNode.properties).map(([key, value]) => (
                            <div key={key} className="flex justify-between text-[13px]">
                                <span className="text-[#999] font-[IBM_Plex_Mono] capitalize">{key}</span>
                                <span className="text-black font-[IBM_Plex_Mono]">{value}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Connections */}
                <div>
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-[11px] font-semibold text-[#999] font-[IBM_Plex_Mono] uppercase tracking-wider">
                            연결
                        </h3>
                        <span className="text-[11px] bg-[#F5F5F5] px-2 py-0.5 rounded text-[#5E5E5E] font-[IBM_Plex_Mono]">
                            {connections.length}
                        </span>
                    </div>
                    <div className="space-y-1.5">
                        {connections.map((conn, idx) => (
                            <div key={idx} className="flex items-center gap-2 text-[13px] p-2 rounded border border-[#E5E5E5] hover:bg-[#F5F5F5] transition-colors">
                                <span className="text-[#999] min-w-[30px] text-xs font-[IBM_Plex_Mono]">
                                    {conn.direction === 'out' ? '→' : '←'}
                                </span>
                                <span className="flex-1 text-black truncate font-[Sora]" title={conn.label}>{conn.label}</span>
                                <span className="text-[10px] text-[#999] bg-[#F5F5F5] px-1.5 py-0.5 rounded font-[IBM_Plex_Mono]">
                                    {conn.relation}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="p-4 border-t border-[#E5E5E5] space-y-2">
                <Button
                    variant="outline"
                    className="w-full text-xs justify-between border-[#E5E5E5] text-[#5E5E5E] hover:bg-[#F5F5F5] font-[Sora]"
                    onClick={() => onFindPath(selectedNode.id)}
                >
                    이 노드로 경로 탐색 <ArrowRight size={14} className="ml-2 opacity-50" />
                </Button>
                <Button
                    variant="outline"
                    className="w-full text-xs justify-between border-[#E5E5E5] text-[#5E5E5E] hover:bg-[#F5F5F5] font-[Sora]"
                    onClick={() => onImpactAnalysis(selectedNode.id)}
                >
                    영향 분석 <Zap size={14} className="ml-2 opacity-50" />
                </Button>
            </div>
        </div>
    );
}
