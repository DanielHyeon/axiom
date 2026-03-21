/**
 * LineagePage — 데이터 리니지 시각화 페이지.
 *
 * 좌측: 엔티티 목록 (타입별 그룹)
 * 중앙: Mermaid 리니지 그래프
 * 우측: 선택 엔티티의 upstream/downstream 패널
 */
import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { GitBranch, ChevronRight, Loader2 } from 'lucide-react';
import { LineageGraphView } from '../components/LineageGraphView';
import type { LineageEntity, LineageEdge } from '../components/LineageGraphView';

// ─── API 함수 ──────────────────────────────────────────────

const BASE = '/api/gateway/olap';

/** 리니지 그래프 전체 조회 */
async function fetchLineageGraph(): Promise<{ entities: LineageEntity[]; edges: LineageEdge[] }> {
  const res = await fetch(`${BASE}/lineage/graph`, { credentials: 'include' });
  const body = await res.json();
  return body.data ?? { entities: [], edges: [] };
}

/** 선택 엔티티의 영향 분석 (upstream/downstream) */
interface ImpactEntity {
  id: string;
  display_name: string;
  edge_type: string;
}

async function fetchImpact(entityId: string): Promise<{ upstream: ImpactEntity[]; downstream: ImpactEntity[] }> {
  const res = await fetch(`${BASE}/lineage/impact/${entityId}`, { credentials: 'include' });
  const body = await res.json();
  return body.data ?? { upstream: [], downstream: [] };
}

// ─── 엔티티 타입 한글 라벨 ─────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
  SOURCE_TABLE: '원천 테이블',
  STAGING_TABLE: '스테이징',
  FACT: '팩트',
  DIMENSION: '차원',
  CUBE: '큐브',
  MEASURE: '측정값',
  DAG: 'DAG',
  REPORT: '리포트',
};

// ─── 컴포넌트 ──────────────────────────────────────────────

export function LineagePage() {
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  // 리니지 그래프 데이터 로드
  const { data: graph, isLoading } = useQuery({
    queryKey: ['olap', 'lineage', 'graph'],
    queryFn: fetchLineageGraph,
  });

  // 선택 엔티티의 영향 분석 데이터 로드
  const { data: impact } = useQuery({
    queryKey: ['olap', 'lineage', 'impact', selectedEntityId],
    queryFn: () => fetchImpact(selectedEntityId!),
    enabled: !!selectedEntityId,
  });

  // 엔티티를 타입별로 그룹핑
  const grouped = useMemo(() => {
    return (graph?.entities ?? []).reduce<Record<string, LineageEntity[]>>((acc, e) => {
      const type = e.entity_type || 'UNKNOWN';
      (acc[type] = acc[type] || []).push(e);
      return acc;
    }, {});
  }, [graph?.entities]);

  return (
    <div className="flex h-full">
      {/* ─── 좌측: 엔티티 목록 사이드바 ────────────────── */}
      <div className="w-[220px] border-r border-[#E5E5E5] flex flex-col shrink-0 bg-white overflow-y-auto">
        {/* 헤더 */}
        <div className="px-3 py-3 border-b border-[#E5E5E5]">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-blue-500" />
            <h2 className="text-[13px] font-semibold font-[Sora]">데이터 리니지</h2>
          </div>
          <span className="text-[10px] text-foreground/40 font-[IBM_Plex_Mono]">
            {graph?.entities?.length ?? 0}개 엔티티
          </span>
        </div>

        {/* 타입별 엔티티 그룹 */}
        {Object.entries(grouped).map(([type, entities]) => (
          <div key={type}>
            {/* 그룹 헤더 */}
            <div className="px-3 py-1.5 text-[9px] text-foreground/40 font-[IBM_Plex_Mono] font-medium bg-[#FAFAFA] border-b border-[#F0F0F0]">
              {TYPE_LABELS[type] || type} ({entities.length})
            </div>
            {/* 개별 엔티티 항목 */}
            {entities.map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => setSelectedEntityId(e.id)}
                className={cn(
                  'flex items-center gap-1.5 w-full text-left px-3 py-1.5 text-[11px] font-[IBM_Plex_Mono] hover:bg-[#F5F5F5] transition-colors',
                  selectedEntityId === e.id && 'bg-blue-50 text-blue-700',
                )}
              >
                <ChevronRight className="h-3 w-3 text-foreground/20 shrink-0" />
                <span className="truncate">{e.display_name}</span>
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* ─── 중앙: 리니지 그래프 ───────────────────────── */}
      <div className="flex-1 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-5 w-5 animate-spin text-foreground/30" />
          </div>
        ) : (
          <LineageGraphView
            entities={graph?.entities ?? []}
            edges={graph?.edges ?? []}
          />
        )}
      </div>

      {/* ─── 우측: 영향 분석 패널 (선택 시에만 표시) ──── */}
      {selectedEntityId && impact && (
        <div className="w-[200px] border-l border-[#E5E5E5] bg-white overflow-y-auto p-3 shrink-0">
          <h3 className="text-[11px] font-semibold font-[Sora] mb-2">영향 분석</h3>

          {/* Upstream 목록 */}
          <div className="mb-3">
            <div className="text-[9px] text-foreground/40 font-[IBM_Plex_Mono] mb-1">
              Upstream ({impact.upstream?.length ?? 0})
            </div>
            {(impact.upstream ?? []).map((u) => (
              <div key={u.id} className="text-[10px] text-foreground/60 font-[IBM_Plex_Mono] py-0.5">
                {u.display_name}
                <span className="text-foreground/30 ml-1">{u.edge_type}</span>
              </div>
            ))}
          </div>

          {/* Downstream 목록 */}
          <div>
            <div className="text-[9px] text-foreground/40 font-[IBM_Plex_Mono] mb-1">
              Downstream ({impact.downstream?.length ?? 0})
            </div>
            {(impact.downstream ?? []).map((d) => (
              <div key={d.id} className="text-[10px] text-foreground/60 font-[IBM_Plex_Mono] py-0.5">
                {d.display_name}
                <span className="text-foreground/30 ml-1">{d.edge_type}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
