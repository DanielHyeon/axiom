import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getImpactAnalysis } from '@/features/ontology/api/ontologyApi';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Zap, X, ChevronDown, ChevronRight, ArrowRight, Loader2 } from 'lucide-react';
import type { OntologyLayer, ImpactNode } from '@/features/ontology/types/ontology';

const LAYER_COLORS: Record<string, string> = {
    kpi: '#EF4444',
    measure: '#F59E0B',
    process: '#3B82F6',
    resource: '#10B981',
    table: '#6B7280',
    column: '#9CA3AF',
    schema: '#A78BFA',
    datasource: '#6366F1',
    unknown: '#525252',
};

interface ImpactAnalysisPanelProps {
    nodeId: string;
    caseId: string;
    onClose: () => void;
}

function DepthGroup({ depth, nodes }: { depth: number; nodes: ImpactNode[] }) {
    const [expanded, setExpanded] = useState(depth <= 2);

    return (
        <div>
            <button
                type="button"
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-2 w-full text-left py-1"
            >
                {expanded ? (
                    <ChevronDown size={14} className="text-[#999]" />
                ) : (
                    <ChevronRight size={14} className="text-[#999]" />
                )}
                <span className="text-sm font-semibold text-black font-[Sora]">{depth}-hop</span>
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                    {nodes.length}
                </Badge>
            </button>
            {expanded && (
                <div className="ml-4 mt-1 space-y-1.5">
                    {nodes.map((node) => (
                        <ImpactNodeRow key={node.id} node={node} />
                    ))}
                </div>
            )}
        </div>
    );
}

function ImpactNodeRow({ node }: { node: ImpactNode }) {
    const layerColor = LAYER_COLORS[node.layer] ?? LAYER_COLORS.unknown;

    return (
        <div className="p-2 rounded border border-[#E5E5E5] hover:bg-[#F5F5F5] transition-colors">
            <div className="flex items-center gap-2">
                <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: layerColor }}
                />
                <span className="text-[13px] text-black flex-1 truncate font-[Sora]" title={node.label}>
                    {node.label}
                </span>
                <Badge variant="outline" className="text-[10px] border-[#E5E5E5] text-[#999] font-[IBM_Plex_Mono]">
                    {node.layer}
                </Badge>
            </div>
            {/* Path breadcrumb */}
            {node.path.length > 1 && (
                <div className="mt-1.5 text-[10px] text-[#999] font-[IBM_Plex_Mono] flex flex-wrap items-center gap-0.5">
                    {node.path.map((step, i) => (
                        <span key={i} className="flex items-center gap-0.5">
                            {i > 0 && step.rel_type && (
                                <>
                                    <span className="text-[#CCC]">{step.rel_type}</span>
                                    <ArrowRight size={8} className="text-[#CCC]" />
                                </>
                            )}
                            <span
                                className={
                                    i === node.path.length - 1
                                        ? 'text-black font-medium'
                                        : ''
                                }
                            >
                                {step.node_label}
                            </span>
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}

export function ImpactAnalysisPanel({ nodeId, caseId, onClose }: ImpactAnalysisPanelProps) {
    const [maxDepth, setMaxDepth] = useState(3);

    const { data, isLoading, isError } = useQuery({
        queryKey: ['impact-analysis', nodeId, caseId, maxDepth],
        queryFn: () => getImpactAnalysis(nodeId, caseId, maxDepth),
    });

    const groupedByDepth = useMemo(() => {
        if (!data?.affected_nodes) return {} as Record<number, ImpactNode[]>;
        const groups: Record<number, ImpactNode[]> = {};
        for (const node of data.affected_nodes) {
            (groups[node.depth] ??= []).push(node);
        }
        return groups;
    }, [data]);

    const depths = useMemo(
        () => Object.keys(groupedByDepth).map(Number).sort((a, b) => a - b),
        [groupedByDepth],
    );

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between h-[52px] px-6 border-b border-[#E5E5E5] shrink-0">
                <div className="flex items-center gap-2">
                    <Zap size={14} className="text-amber-500" />
                    <span className="text-[13px] font-semibold text-black font-[Sora]">영향 분석</span>
                </div>
                <button
                    type="button"
                    onClick={onClose}
                    className="text-[#999] hover:text-black text-lg transition-colors"
                >
                    ×
                </button>
            </div>

            {/* Root info */}
            {data?.root && (
                <div className="px-6 py-3 border-b border-[#E5E5E5]">
                    <p className="text-[13px] text-[#5E5E5E] font-[IBM_Plex_Mono]">
                        {data.root.label}{' '}
                        <span
                            className="inline-block w-1.5 h-1.5 rounded-full ml-1 align-middle"
                            style={{
                                backgroundColor:
                                    LAYER_COLORS[data.root.layer as OntologyLayer] ?? LAYER_COLORS.unknown,
                            }}
                        />
                        <span className="ml-1">{data.root.layer}</span>
                    </p>
                </div>
            )}

            {/* Summary */}
            {data && (
                <div className="px-6 py-3 border-b border-[#E5E5E5] flex gap-4 text-[11px] text-[#999] font-[IBM_Plex_Mono]">
                    <span>영향 노드: {data.total_affected}</span>
                    <span>최대 깊이: {data.max_depth_reached}</span>
                    <span>{data.analysis_time_ms}ms</span>
                </div>
            )}

            {/* Depth Slider */}
            <div className="px-6 py-3 border-b border-[#E5E5E5]">
                <label className="text-[11px] text-[#999] font-[IBM_Plex_Mono] block mb-2">
                    탐색 깊이: {maxDepth}
                </label>
                <Slider
                    min={1}
                    max={5}
                    step={1}
                    value={[maxDepth]}
                    onValueChange={(val) => setMaxDepth(val[0])}
                />
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {isLoading && (
                    <div className="flex flex-col items-center justify-center py-12 text-[#999]">
                        <Loader2 size={24} className="animate-spin mb-2" />
                        <p className="text-sm font-[IBM_Plex_Mono]">BFS 탐색 중...</p>
                    </div>
                )}

                {isError && (
                    <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-600">
                        영향 분석에 실패했습니다.
                    </div>
                )}

                {data && data.total_affected === 0 && !isLoading && (
                    <div className="text-center py-8 text-[#999] text-sm font-[IBM_Plex_Mono]">
                        연결된 영향 노드가 없습니다.
                    </div>
                )}

                {depths.map((depth) => (
                    <DepthGroup key={depth} depth={depth} nodes={groupedByDepth[depth]} />
                ))}
            </div>
        </div>
    );
}
