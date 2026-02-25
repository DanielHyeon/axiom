import { useState, useMemo, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { ROUTES } from '@/lib/routes/routes';
import { useOntologyData } from '@/features/ontology/hooks/useOntologyData';
import { exportOntology } from '@/features/ontology/api/ontologyApi';
import { GraphViewer } from './components/GraphViewer';
import { SearchPanel } from './components/SearchPanel';
import { LayerFilter } from './components/LayerFilter';
import { NodeDetail } from './components/NodeDetail';
import { ImpactAnalysisPanel } from './components/ImpactAnalysisPanel';
import { PathHighlighter } from './components/PathHighlighter';
import { ConceptMapView } from './components/ConceptMapView';
import { QualityDashboard } from './components/QualityDashboard';
import { HITLReviewQueue } from './components/HITLReviewQueue';
import { Share2, ShieldCheck, ClipboardList, Download } from 'lucide-react';
import type { ViewMode } from '@/features/ontology/types/ontology';

const VIEW_MODES: { key: ViewMode; label: string }[] = [
    { key: 'graph', label: '그래프' },
    { key: 'conceptMap', label: '매핑' },
    { key: 'table', label: '테이블' },
];

export function OntologyPage() {
    const [searchParams] = useSearchParams();
    const caseId = searchParams.get('caseId');

    const { filters, viewMode, setViewMode, setCaseId } = useOntologyStore();
    const { getFilteredGraph, findShortestPath, isLoading } = useOntologyData(caseId);
    const [pathNodeIds, setPathNodeIds] = useState<string[]>([]);
    const [pathModeSource, setPathModeSource] = useState<string | null>(null);
    const [impactNodeId, setImpactNodeId] = useState<string | null>(null);
    const [showQuality, setShowQuality] = useState(false);
    const [showHITL, setShowHITL] = useState(false);

    // Sync caseId from URL to store so child components can access it
    useEffect(() => {
        setCaseId(caseId);
    }, [caseId, setCaseId]);

    // Get live filtered data
    const filteredData = useMemo(() => {
        return getFilteredGraph(filters.query, filters.layers);
    }, [getFilteredGraph, filters]);

    const handleFindPath = async (targetId: string) => {
        if (!pathModeSource) {
            setPathModeSource(targetId);
            setPathNodeIds([targetId]);
        } else {
            const path = await findShortestPath(pathModeSource, targetId);
            setPathNodeIds(path);
            setPathModeSource(null);
        }
    };

    const clearPath = () => {
        setPathNodeIds([]);
        setPathModeSource(null);
    };

    const handleExport = async (format: 'turtle' | 'jsonld') => {
        if (!caseId) return;
        const blob = await exportOntology(caseId, format);
        const ext = format === 'turtle' ? 'ttl' : 'jsonld';
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ontology-${caseId}.${ext}`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const navigate = useNavigate();

    if (!caseId) {
        return <CaseSelector onSelect={(id) => navigate(ROUTES.DATA.ONTOLOGY_CASE(id))} />;
    }

    return (
        <div className="flex flex-col h-full bg-[#111111] overflow-hidden">
            {/* Header / Controls */}
            <div className="h-14 border-b border-neutral-800 bg-[#161616] flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-2">
                    <Share2 className="text-neutral-400 mr-2" size={20} />
                    <h1 className="text-base font-bold text-neutral-200">K-AIR 온톨로지 탐색</h1>
                </div>

                <div className="flex items-center gap-4">
                    {/* 3-mode tabs */}
                    <div className="flex bg-neutral-900 rounded-lg p-0.5">
                        {VIEW_MODES.map((mode) => (
                            <button
                                type="button"
                                key={mode.key}
                                onClick={() => setViewMode(mode.key)}
                                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                                    viewMode === mode.key
                                        ? 'bg-neutral-700 text-neutral-100'
                                        : 'text-neutral-500 hover:text-neutral-300'
                                }`}
                            >
                                {mode.label}
                            </button>
                        ))}
                    </div>
                    {viewMode === 'graph' && <LayerFilter />}
                    {viewMode === 'graph' && <SearchPanel />}

                    {/* O5: Governance tools */}
                    <div className="flex items-center gap-1 border-l border-neutral-700 pl-3">
                        <button
                            type="button"
                            onClick={() => { setShowQuality(!showQuality); setShowHITL(false); }}
                            className={`p-1.5 rounded-md transition-colors ${
                                showQuality ? 'bg-neutral-700 text-neutral-100' : 'text-neutral-500 hover:text-neutral-300'
                            }`}
                            title="데이터 품질"
                        >
                            <ShieldCheck size={16} />
                        </button>
                        <button
                            type="button"
                            onClick={() => { setShowHITL(!showHITL); setShowQuality(false); }}
                            className={`p-1.5 rounded-md transition-colors ${
                                showHITL ? 'bg-neutral-700 text-neutral-100' : 'text-neutral-500 hover:text-neutral-300'
                            }`}
                            title="검토 대기열"
                        >
                            <ClipboardList size={16} />
                        </button>
                        <div className="relative group">
                            <button
                                type="button"
                                className="p-1.5 rounded-md text-neutral-500 hover:text-neutral-300 transition-colors"
                                title="내보내기"
                            >
                                <Download size={16} />
                            </button>
                            <div className="absolute right-0 top-full mt-1 hidden group-hover:block bg-neutral-900 border border-neutral-700 rounded-lg shadow-xl py-1 z-50 min-w-[140px]">
                                <button
                                    type="button"
                                    className="w-full text-left px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
                                    onClick={() => handleExport('turtle')}
                                >
                                    Turtle (.ttl)
                                </button>
                                <button
                                    type="button"
                                    className="w-full text-left px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
                                    onClick={() => handleExport('jsonld')}
                                >
                                    JSON-LD (.jsonld)
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {viewMode === 'graph' && (
                <PathHighlighter
                    pathNodeIds={pathNodeIds}
                    pathModeSource={pathModeSource}
                    onClear={clearPath}
                />
            )}

            {/* Main Content Area */}
            <div className="flex-1 flex overflow-hidden">
                {isLoading ? (
                    <div className="flex-1 flex items-center justify-center text-neutral-500 text-sm">
                        온톨로지 데이터 로딩 중...
                    </div>
                ) : viewMode === 'graph' ? (
                    <GraphViewer
                        data={filteredData}
                        shortestPathIds={pathModeSource ? [] : pathNodeIds}
                    />
                ) : viewMode === 'conceptMap' ? (
                    <ConceptMapView caseId={caseId} />
                ) : (
                    <div className="flex-1 p-8 text-neutral-400 flex items-center justify-center">
                        접근성을 위한 테이블 뷰 (구현 예정)
                    </div>
                )}

                {viewMode === 'graph' && !impactNodeId && (
                    <NodeDetail
                        onFindPath={handleFindPath}
                        onImpactAnalysis={(nodeId) => setImpactNodeId(nodeId)}
                    />
                )}
                {viewMode === 'graph' && impactNodeId && caseId && (
                    <ImpactAnalysisPanel
                        nodeId={impactNodeId}
                        caseId={caseId}
                        onClose={() => setImpactNodeId(null)}
                    />
                )}

                {showQuality && caseId && (
                    <QualityDashboard caseId={caseId} onClose={() => setShowQuality(false)} />
                )}
                {showHITL && caseId && (
                    <HITLReviewQueue caseId={caseId} onClose={() => setShowHITL(false)} />
                )}
            </div>
        </div>
    );
}

function CaseSelector({ onSelect }: { onSelect: (caseId: string) => void }) {
    const { data: cases, isLoading } = useCases();

    return (
        <div className="flex flex-col items-center justify-center h-full text-neutral-500 gap-4">
            <Share2 size={32} className="opacity-20" />
            <p className="text-sm font-medium text-neutral-400">온톨로지를 탐색할 케이스를 선택하세요</p>
            {isLoading ? (
                <div className="h-8 w-48 animate-pulse rounded bg-neutral-800" />
            ) : cases && cases.length > 0 ? (
                <div className="flex flex-col gap-2 w-full max-w-sm">
                    {cases.map((c) => (
                        <button
                            key={c.id}
                            type="button"
                            onClick={() => onSelect(c.id)}
                            className="flex items-center justify-between px-4 py-3 rounded-lg border border-neutral-800 bg-neutral-900/50 hover:bg-neutral-800 hover:border-neutral-700 transition-colors text-left"
                        >
                            <span className="text-sm text-neutral-200 truncate">{c.title}</span>
                            <span className="text-xs text-neutral-600 shrink-0 ml-2">{c.status}</span>
                        </button>
                    ))}
                </div>
            ) : (
                <p className="text-xs text-neutral-600">등록된 케이스가 없습니다.</p>
            )}
        </div>
    );
}
