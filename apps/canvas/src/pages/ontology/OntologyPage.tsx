import { useState, useMemo } from 'react';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import { useOntologyMock } from '@/features/ontology/hooks/useOntologyMock';
import { GraphViewer } from './components/GraphViewer';
import { SearchPanel } from './components/SearchPanel';
import { LayerFilter } from './components/LayerFilter';
import { NodeDetail } from './components/NodeDetail';
import { PathHighlighter } from './components/PathHighlighter';
import { Share2 } from 'lucide-react';

export function OntologyPage() {
    const { filters, isTableMode } = useOntologyStore();
    const { getFilteredGraph, findShortestPath } = useOntologyMock();
    const [pathNodeIds, setPathNodeIds] = useState<string[]>([]);
    const [pathModeSource, setPathModeSource] = useState<string | null>(null);

    // Get live filtered data
    const filteredData = useMemo(() => {
        return getFilteredGraph(filters.query, filters.layers);
    }, [getFilteredGraph, filters]);

    const handleFindPath = (targetId: string) => {
        if (!pathModeSource) {
            // First click sets source, UI indicates waiting for target
            setPathModeSource(targetId);
            setPathNodeIds([targetId]);
        } else {
            // Second click evaluates path
            const path = findShortestPath(pathModeSource, targetId);
            setPathNodeIds(path);
            setPathModeSource(null); // Reset mode
        }
    };

    const clearPath = () => {
        setPathNodeIds([]);
        setPathModeSource(null);
    };

    return (
        <div className="flex flex-col h-full bg-[#111111] overflow-hidden">
            {/* Header / Controls */}
            <div className="h-14 border-b border-neutral-800 bg-[#161616] flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-2">
                    <Share2 className="text-neutral-400 mr-2" size={20} />
                    <h1 className="text-base font-bold text-neutral-200">K-AIR 온톨로지 탐색</h1>
                </div>

                <div className="flex items-center gap-4">
                    <LayerFilter />
                    <SearchPanel />
                </div>
            </div>

            <PathHighlighter
                pathNodeIds={pathNodeIds}
                pathModeSource={pathModeSource}
                onClear={clearPath}
            />

            {/* Main Content Area */}
            <div className="flex-1 flex overflow-hidden">
                {isTableMode ? (
                    <div className="flex-1 p-8 text-neutral-400 flex items-center justify-center">
                        접근성을 위한 테이블 뷰 (구현 예정)
                    </div>
                ) : (
                    <GraphViewer
                        data={filteredData}
                        shortestPathIds={pathModeSource ? [] : pathNodeIds}
                    />
                )}

                <NodeDetail onFindPath={handleFindPath} />
            </div>
        </div>
    );
}
