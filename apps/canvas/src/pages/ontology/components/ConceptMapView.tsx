import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    getConceptMappings,
    createConceptMapping,
    deleteConceptMapping,
    getSchemaEntities,
} from '@/features/ontology/api/ontologyApi';
import { useOntologyData } from '@/features/ontology/hooks/useOntologyData';
import { BipartiteGraphView } from './BipartiteGraphView';
import { Trash2, Plus, Link, List, GitBranch } from 'lucide-react';
import type { ConceptMapSubView } from '@/features/ontology/types/ontology';

interface ConceptMapViewProps {
    caseId: string;
}

export function ConceptMapView({ caseId }: ConceptMapViewProps) {
    const queryClient = useQueryClient();

    // Existing mappings
    const { data: mappings = [], isLoading: mappingsLoading } = useQuery({
        queryKey: ['concept-mappings', caseId],
        queryFn: () => getConceptMappings(caseId),
    });

    // Schema entities (tables)
    const { data: tables = [] } = useQuery({
        queryKey: ['schema-entities'],
        queryFn: () => getSchemaEntities(),
    });

    // Ontology nodes from current graph
    const { graphData } = useOntologyData(caseId);

    // Sub-view toggle
    const [subView, setSubView] = useState<ConceptMapSubView>('table');

    // Form state
    const [selectedSourceId, setSelectedSourceId] = useState('');
    const [selectedTargetTable, setSelectedTargetTable] = useState('');
    const [relType, setRelType] = useState('MAPS_TO');

    // Mutations
    const createMut = useMutation({
        mutationFn: ({ src, tgt, rel }: { src: string; tgt: string; rel: string }) =>
            createConceptMapping(src, tgt, rel),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['concept-mappings'] });
            setSelectedSourceId('');
            setSelectedTargetTable('');
        },
    });

    const deleteMut = useMutation({
        mutationFn: (relId: string) => deleteConceptMapping(relId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['concept-mappings'] }),
    });

    const handleCreate = () => {
        if (!selectedSourceId || !selectedTargetTable) return;
        createMut.mutate({ src: selectedSourceId, tgt: selectedTargetTable, rel: relType });
    };

    return (
        <div className="flex-1 flex flex-col overflow-hidden p-4 gap-4">
            {/* Create mapping form */}
            <div className="bg-[#F5F5F5] border border-[#E5E5E5] rounded p-4">
                <h3 className="text-sm font-semibold text-black font-[Sora] mb-3 flex items-center gap-2">
                    <Plus size={14} />
                    새 매핑 추가
                </h3>
                <div className="flex items-end gap-3">
                    {/* Source: Ontology Node */}
                    <div className="flex-1">
                        <label className="block text-[11px] text-[#999] font-[IBM_Plex_Mono] mb-1">온톨로지 노드</label>
                        <select
                            value={selectedSourceId}
                            onChange={(e) => setSelectedSourceId(e.target.value)}
                            className="w-full bg-white text-black text-[13px] rounded border border-[#E5E5E5] px-2 py-1.5 font-[IBM_Plex_Mono] focus:outline-none focus:border-[#999]"
                        >
                            <option value="">노드 선택...</option>
                            {graphData.nodes.map((node) => (
                                <option key={node.id} value={node.id}>
                                    [{node.layer}] {node.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Relation type */}
                    <div className="w-36">
                        <label className="block text-[11px] text-[#999] font-[IBM_Plex_Mono] mb-1">관계 유형</label>
                        <select
                            value={relType}
                            onChange={(e) => setRelType(e.target.value)}
                            className="w-full bg-white text-black text-[13px] rounded border border-[#E5E5E5] px-2 py-1.5 font-[IBM_Plex_Mono] focus:outline-none focus:border-[#999]"
                        >
                            <option value="MAPS_TO">MAPS_TO</option>
                            <option value="DERIVED_FROM">DERIVED_FROM</option>
                            <option value="DEFINES">DEFINES</option>
                        </select>
                    </div>

                    {/* Target: Table */}
                    <div className="flex-1">
                        <label className="block text-[11px] text-[#999] font-[IBM_Plex_Mono] mb-1">스키마 테이블</label>
                        <select
                            value={selectedTargetTable}
                            onChange={(e) => setSelectedTargetTable(e.target.value)}
                            className="w-full bg-white text-black text-[13px] rounded border border-[#E5E5E5] px-2 py-1.5 font-[IBM_Plex_Mono] focus:outline-none focus:border-[#999]"
                        >
                            <option value="">테이블 선택...</option>
                            {tables.map((t) => (
                                <option key={`${t.datasource}.${t.schema}.${t.name}`} value={t.name}>
                                    {t.schema}.{t.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    <button
                        type="button"
                        onClick={handleCreate}
                        disabled={!selectedSourceId || !selectedTargetTable || createMut.isPending}
                        className="px-4 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-[#E5E5E5] disabled:text-[#999] text-white text-[12px] font-medium font-[Sora] rounded transition-colors"
                    >
                        {createMut.isPending ? '...' : '추가'}
                    </button>
                </div>
                {createMut.isError && (
                    <p className="text-xs text-red-500 mt-2 font-[IBM_Plex_Mono]">매핑 생성 실패. 노드 또는 테이블을 확인하세요.</p>
                )}
            </div>

            {/* Sub-view toggle */}
            <div className="flex items-center gap-1 bg-[#F5F5F5] rounded p-0.5 w-fit">
                <button
                    type="button"
                    onClick={() => setSubView('table')}
                    className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium font-[Sora] rounded transition-colors ${
                        subView === 'table'
                            ? 'bg-white text-black shadow-sm'
                            : 'text-[#999] hover:text-[#666]'
                    }`}
                >
                    <List size={14} />
                    테이블
                </button>
                <button
                    type="button"
                    onClick={() => setSubView('visual')}
                    className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium font-[Sora] rounded transition-colors ${
                        subView === 'visual'
                            ? 'bg-white text-black shadow-sm'
                            : 'text-[#999] hover:text-[#666]'
                    }`}
                >
                    <GitBranch size={14} />
                    시각화
                </button>
            </div>

            {/* Content: visual or table */}
            {subView === 'visual' ? (
                <BipartiteGraphView
                    mappings={mappings}
                    ontologyNodes={graphData.nodes}
                    tables={tables}
                />
            ) : (
            <div className="flex-1 overflow-auto">
                <table className="w-full text-[13px]">
                    <thead>
                        <tr className="text-[11px] text-[#999] font-[IBM_Plex_Mono] uppercase border-b border-[#E5E5E5]">
                            <th className="text-left py-2 px-3 font-medium">소스 노드</th>
                            <th className="text-left py-2 px-3 font-medium">레이어</th>
                            <th className="text-left py-2 px-3 font-medium">관계</th>
                            <th className="text-left py-2 px-3 font-medium">대상 테이블</th>
                            <th className="text-left py-2 px-3 font-medium">스키마</th>
                            <th className="text-left py-2 px-3 font-medium">생성일</th>
                            <th className="w-10"></th>
                        </tr>
                    </thead>
                    <tbody>
                        {mappingsLoading ? (
                            <tr>
                                <td colSpan={7} className="text-center py-8 text-[#999]">
                                    로딩 중...
                                </td>
                            </tr>
                        ) : mappings.length === 0 ? (
                            <tr>
                                <td colSpan={7} className="text-center py-8 text-[#999]">
                                    <Link size={20} className="inline-block mb-1 opacity-30" />
                                    <p className="font-[IBM_Plex_Mono]">매핑이 없습니다. 위에서 새 매핑을 추가하세요.</p>
                                </td>
                            </tr>
                        ) : (
                            mappings.map((m) => (
                                <tr
                                    key={m.rel_id}
                                    className="border-b border-[#E5E5E5] hover:bg-[#F5F5F5] transition-colors"
                                >
                                    <td className="py-2 px-3 text-black font-[Sora]">{m.source_name}</td>
                                    <td className="py-2 px-3">
                                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#F5F5F5] text-[#5E5E5E] font-[IBM_Plex_Mono]">
                                            {m.source_layer}
                                        </span>
                                    </td>
                                    <td className="py-2 px-3">
                                        <span className="text-[11px] text-blue-600 font-[IBM_Plex_Mono]">{m.rel_type}</span>
                                    </td>
                                    <td className="py-2 px-3 text-black font-[IBM_Plex_Mono]">{m.target_table}</td>
                                    <td className="py-2 px-3 text-[#999] font-[IBM_Plex_Mono]">{m.target_schema ?? '-'}</td>
                                    <td className="py-2 px-3 text-[#999] text-xs font-[IBM_Plex_Mono]">
                                        {m.created_at ? new Date(m.created_at).toLocaleDateString() : '-'}
                                    </td>
                                    <td className="py-2 px-1">
                                        <button
                                            type="button"
                                            onClick={() => deleteMut.mutate(m.rel_id)}
                                            disabled={deleteMut.isPending}
                                            className="p-1 text-[#999] hover:text-red-500 transition-colors"
                                            title="매핑 삭제"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            )}
        </div>
    );
}
