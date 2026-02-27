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
import { Share2, ShieldCheck, ClipboardList, Download, Plus, Search } from 'lucide-react';
import type { ViewMode } from '@/features/ontology/types/ontology';

const VIEW_MODES: { key: ViewMode; label: string }[] = [
    { key: 'graph', label: 'All' },
    { key: 'conceptMap', label: 'Platform' },
    { key: 'table', label: 'API' },
];

const LAYER_TABS = ['All', 'Metrics', 'KPI', 'Measure', 'Resource'];

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
    const [activeLayerTab, setActiveLayerTab] = useState('All');

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
        <div className="flex flex-col h-full overflow-hidden">
            {/* Content Body */}
            <div className="flex-1 flex flex-col overflow-hidden px-12 py-8 gap-8">
                {/* Title Row */}
                <div className="flex items-start justify-between">
                    <div className="space-y-1.5">
                        <h1 className="text-[48px] font-semibold tracking-[-2px] text-black font-[Sora]">Ontology</h1>
                        <p className="text-[13px] text-[#5E5E5E] font-[IBM_Plex_Mono]">
                            K-MRI 온톨로지 지식 그래프를 탐색하고 관리합니다
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2 px-4 py-2.5 border border-[#E5E5E5] rounded">
                            <Search className="h-3.5 w-3.5 text-[#999]" />
                            <span className="text-[13px] text-[#999] font-[IBM_Plex_Mono]">노드 검색...</span>
                        </div>
                        <button
                            type="button"
                            className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white text-[12px] font-medium font-[Sora] rounded hover:bg-red-700 transition-colors"
                        >
                            <Plus className="h-3.5 w-3.5" />
                            노드 추가
                        </button>
                    </div>
                </div>

                {/* Filter Tabs */}
                <div className="flex items-center gap-2.5">
                    <span className="text-[11px] font-semibold text-[#999] font-[IBM_Plex_Mono] uppercase tracking-wider">Filter</span>
                    {LAYER_TABS.map((tab) => (
                        <button
                            key={tab}
                            type="button"
                            onClick={() => setActiveLayerTab(tab)}
                            className={`px-4 py-2.5 text-[12px] font-[Sora] transition-colors ${
                                activeLayerTab === tab
                                    ? 'text-black font-semibold border-b-2 border-red-600'
                                    : 'text-[#999] hover:text-[#666]'
                            }`}
                        >
                            {tab}
                        </button>
                    ))}

                    {/* Governance tools */}
                    <div className="ml-auto flex items-center gap-1">
                        <button
                            type="button"
                            onClick={() => { setShowQuality(!showQuality); setShowHITL(false); }}
                            className={`p-2 rounded transition-colors ${
                                showQuality ? 'bg-[#F5F5F5] text-black' : 'text-[#999] hover:text-[#666]'
                            }`}
                            title="데이터 품질"
                        >
                            <ShieldCheck size={16} />
                        </button>
                        <button
                            type="button"
                            onClick={() => { setShowHITL(!showHITL); setShowQuality(false); }}
                            className={`p-2 rounded transition-colors ${
                                showHITL ? 'bg-[#F5F5F5] text-black' : 'text-[#999] hover:text-[#666]'
                            }`}
                            title="검토 대기열"
                        >
                            <ClipboardList size={16} />
                        </button>
                        <div className="relative group">
                            <button
                                type="button"
                                className="p-2 rounded text-[#999] hover:text-[#666] transition-colors"
                                title="내보내기"
                            >
                                <Download size={16} />
                            </button>
                            <div className="absolute right-0 top-full mt-1 hidden group-hover:block bg-white border border-[#E5E5E5] rounded-lg shadow-lg py-1 z-50 min-w-[140px]">
                                <button
                                    type="button"
                                    className="w-full text-left px-3 py-1.5 text-xs text-[#333] hover:bg-[#F5F5F5]"
                                    onClick={() => handleExport('turtle')}
                                >
                                    Turtle (.ttl)
                                </button>
                                <button
                                    type="button"
                                    className="w-full text-left px-3 py-1.5 text-xs text-[#333] hover:bg-[#F5F5F5]"
                                    onClick={() => handleExport('jsonld')}
                                >
                                    JSON-LD (.jsonld)
                                </button>
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

                {/* Main Content Area: Graph + Detail panel */}
                <div className="flex-1 flex overflow-hidden rounded border border-[#E5E5E5]">
                    {isLoading ? (
                        <div className="flex-1 flex items-center justify-center text-[#999] text-sm">
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
                        <div className="flex-1 p-8 text-[#999] flex items-center justify-center">
                            접근성을 위한 테이블 뷰 (구현 예정)
                        </div>
                    )}

                    {/* Right panel: Node detail or Impact analysis */}
                    {viewMode === 'graph' && !impactNodeId && (
                        <div className="w-80 shrink-0 border-l border-[#E5E5E5] bg-white overflow-y-auto flex flex-col">
                            <NodeDetail
                                onFindPath={handleFindPath}
                                onImpactAnalysis={(nodeId) => setImpactNodeId(nodeId)}
                            />
                        </div>
                    )}
                    {viewMode === 'graph' && impactNodeId && caseId && (
                        <div className="w-80 shrink-0 border-l border-[#E5E5E5] bg-white overflow-y-auto flex flex-col">
                            <ImpactAnalysisPanel
                                nodeId={impactNodeId}
                                caseId={caseId}
                                onClose={() => setImpactNodeId(null)}
                            />
                        </div>
                    )}

                    {showQuality && caseId && (
                        <div className="w-80 shrink-0 border-l border-[#E5E5E5] bg-white overflow-y-auto flex flex-col">
                            <QualityDashboard caseId={caseId} onClose={() => setShowQuality(false)} />
                        </div>
                    )}
                    {showHITL && caseId && (
                        <div className="w-80 shrink-0 border-l border-[#E5E5E5] bg-white overflow-y-auto flex flex-col">
                            <HITLReviewQueue caseId={caseId} onClose={() => setShowHITL(false)} />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function CaseSelector({ onSelect }: { onSelect: (caseId: string) => void }) {
    const { data: cases, isLoading } = useCases();

    return (
        <div className="flex flex-col items-center justify-center h-full text-[#999] gap-4">
            <Share2 size={32} className="opacity-20" />
            <p className="text-sm font-medium text-[#666]">온톨로지를 탐색할 케이스를 선택하세요</p>
            {isLoading ? (
                <div className="h-8 w-48 animate-pulse rounded bg-[#F5F5F5]" />
            ) : cases && cases.length > 0 ? (
                <div className="flex flex-col gap-2 w-full max-w-sm">
                    {cases.map((c) => (
                        <button
                            key={c.id}
                            type="button"
                            onClick={() => onSelect(c.id)}
                            className="flex items-center justify-between px-4 py-3 rounded-lg border border-[#E5E5E5] bg-white hover:bg-[#F5F5F5] hover:border-[#CCC] transition-colors text-left"
                        >
                            <span className="text-sm text-black truncate">{c.title}</span>
                            <span className="text-xs text-[#999] shrink-0 ml-2">{c.status}</span>
                        </button>
                    ))}
                </div>
            ) : (
                <p className="text-xs text-[#999]">등록된 케이스가 없습니다.</p>
            )}
        </div>
    );
}
