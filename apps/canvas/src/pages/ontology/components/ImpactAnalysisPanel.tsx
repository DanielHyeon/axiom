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
                    <ChevronDown size={14} className="text-neutral-500" />
                ) : (
                    <ChevronRight size={14} className="text-neutral-500" />
                )}
                <span className="text-sm font-semibold text-neutral-300">{depth}-hop</span>
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
        <div className="bg-[#1a1a1a] p-2 rounded border border-neutral-800/30 hover:border-neutral-700 transition-colors">
            <div className="flex items-center gap-2">
                <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: layerColor }}
                />
                <span className="text-sm text-neutral-200 flex-1 truncate" title={node.label}>
                    {node.label}
                </span>
                <Badge variant="outline" className="text-[10px] border-neutral-700 text-neutral-500">
                    {node.layer}
                </Badge>
            </div>
            {/* Path breadcrumb */}
            {node.path.length > 1 && (
                <div className="mt-1.5 text-[10px] text-neutral-500 flex flex-wrap items-center gap-0.5">
                    {node.path.map((step, i) => (
                        <span key={i} className="flex items-center gap-0.5">
                            {i > 0 && step.rel_type && (
                                <>
                                    <span className="text-neutral-600">{step.rel_type}</span>
                                    <ArrowRight size={8} className="text-neutral-600" />
                                </>
                            )}
                            <span
                                className={
                                    i === node.path.length - 1
                                        ? 'text-neutral-300 font-medium'
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
        <div className="w-96 border-l border-neutral-800 bg-[#161616] flex flex-col h-full overflow-hidden">
            {/* Header */}
            <div className="p-5 border-b border-neutral-800 bg-[#1a1a1a]">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Zap size={16} className="text-amber-400" />
                        <h2 className="text-lg font-bold text-neutral-100">영향 분석</h2>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="p-1 text-neutral-500 hover:text-neutral-300 transition-colors"
                    >
                        <X size={18} />
                    </button>
                </div>
                {data?.root && (
                    <p className="text-xs text-neutral-500 mt-1">
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
                )}
            </div>

            {/* Summary */}
            {data && (
                <div className="px-5 py-3 border-b border-neutral-800/50 flex gap-4 text-xs text-neutral-400">
                    <span>영향 노드: {data.total_affected}</span>
                    <span>최대 깊이: {data.max_depth_reached}</span>
                    <span>{data.analysis_time_ms}ms</span>
                </div>
            )}

            {/* Depth Slider */}
            <div className="px-5 py-3 border-b border-neutral-800/50">
                <label className="text-xs text-neutral-500 block mb-2">
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
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {isLoading && (
                    <div className="flex flex-col items-center justify-center py-12 text-neutral-500">
                        <Loader2 size={24} className="animate-spin mb-2" />
                        <p className="text-sm">BFS 탐색 중...</p>
                    </div>
                )}

                {isError && (
                    <div className="rounded border border-red-900/50 bg-red-900/20 p-3 text-sm text-red-200">
                        영향 분석에 실패했습니다.
                    </div>
                )}

                {data && data.total_affected === 0 && !isLoading && (
                    <div className="text-center py-8 text-neutral-600 text-sm">
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
