/**
 * 시멘틱 카탈로그 페이지 — 개념/지표/차원/조인 브라우저
 *
 * Control Plane에서 정의한 시멘틱 계약을 조회하고 관리한다.
 * 개념 상태 전이(draft→review→approved), 지표 컴파일, 배포 등을 지원.
 */
import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2, BookOpen } from 'lucide-react';
import {
  useSemanticCatalog,
  useConcepts,
  useMeasures,
  useDimensions,
  useJoins,
  useChangeConceptStatus,
  useCompileMeasure,
  usePublish,
} from '@/features/semantic-catalog/hooks/useSemanticCatalog';
import { CatalogSummaryCards } from '@/features/semantic-catalog/components/CatalogSummaryCards';
import { ConceptTable } from '@/features/semantic-catalog/components/ConceptTable';
import { MeasureTable } from '@/features/semantic-catalog/components/MeasureTable';
import { StatusBadge } from '@/features/semantic-catalog/components/StatusBadge';
import type { ConceptStatus, CompileResult } from '@/features/semantic-catalog/types/semantic';

type TabKey = 'concepts' | 'entities' | 'measures' | 'dimensions' | 'joins' | 'grains';

export function SemanticCatalogPage() {
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('case_id') || undefined;

  const [activeTab, setActiveTab] = useState<TabKey>('concepts');

  // 데이터 조회
  const { data: catalog, isLoading: catalogLoading } = useSemanticCatalog(caseId);
  const { data: concepts = [] } = useConcepts({ case_id: caseId });
  const { data: measures = [] } = useMeasures({ case_id: caseId });
  const { data: dimensions = [] } = useDimensions({ case_id: caseId });
  const { data: joins = [] } = useJoins({ case_id: caseId });

  // 뮤테이션
  const statusMutation = useChangeConceptStatus();
  const compileMutation = useCompileMeasure();
  const publishMutation = usePublish();

  const handleStatusChange = useCallback(
    (conceptId: string, newStatus: ConceptStatus) => {
      statusMutation.mutate({ conceptId, status: newStatus });
    },
    [statusMutation],
  );

  const handleCompile = useCallback(
    async (measureId: string): Promise<CompileResult> => {
      return compileMutation.mutateAsync(measureId);
    },
    [compileMutation],
  );

  const handlePublish = useCallback(
    (measureId: string) => {
      publishMutation.mutate({ objectType: 'measure', objectId: measureId });
    },
    [publishMutation],
  );

  if (catalogLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const summary = catalog?.summary ?? {
    concepts: 0, entities: 0, measures: 0, dimensions: 0, joins: 0, grains: 0,
  };

  return (
    <div className="flex flex-col gap-4 p-4 h-full overflow-auto">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <BookOpen className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-xl font-bold">시멘틱 카탈로그</h1>
          <p className="text-sm text-muted-foreground">
            온톨로지 개념 · 시멘틱 지표 · 차원 · 조인 계약을 관리합니다
          </p>
        </div>
      </div>

      {/* 요약 카드 */}
      <CatalogSummaryCards summary={summary} activeTab={activeTab} onTabChange={(t) => setActiveTab(t as TabKey)} />

      {/* 탭별 내용 */}
      <div className="flex-1 min-h-0">
        {activeTab === 'concepts' && (
          <ConceptTable
            concepts={concepts}
            onStatusChange={handleStatusChange}
            isStatusChanging={statusMutation.isPending}
          />
        )}

        {activeTab === 'measures' && (
          <MeasureTable
            measures={measures}
            onCompile={handleCompile}
            onPublish={handlePublish}
            isPublishing={publishMutation.isPending}
          />
        )}

        {activeTab === 'dimensions' && (
          <div className="rounded-lg border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium">차원 ID</th>
                  <th className="px-3 py-2 text-left font-medium">이름</th>
                  <th className="px-3 py-2 text-left font-medium">타입</th>
                  <th className="px-3 py-2 text-left font-medium">SQL 표현식</th>
                  <th className="px-3 py-2 text-left font-medium">계층</th>
                  <th className="px-3 py-2 text-left font-medium">상태</th>
                </tr>
              </thead>
              <tbody>
                {dimensions.map((d) => (
                  <tr key={d.dimension_id} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-2 font-mono text-xs">{d.dimension_id}</td>
                    <td className="px-3 py-2 font-medium">{d.name}</td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">{d.value_type}</span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground max-w-[300px] truncate">
                      {d.sql_expression}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{d.hierarchy_path || '—'}</td>
                    <td className="px-3 py-2"><StatusBadge status={d.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {dimensions.length === 0 && (
              <div className="py-8 text-center text-muted-foreground text-sm">등록된 차원이 없습니다</div>
            )}
          </div>
        )}

        {activeTab === 'joins' && (
          <div className="rounded-lg border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium">조인 ID</th>
                  <th className="px-3 py-2 text-left font-medium">Left → Right</th>
                  <th className="px-3 py-2 text-left font-medium">타입</th>
                  <th className="px-3 py-2 text-left font-medium">조건</th>
                  <th className="px-3 py-2 text-center font-medium">AI 허용</th>
                  <th className="px-3 py-2 text-center font-medium">Fanout</th>
                </tr>
              </thead>
              <tbody>
                {joins.map((j) => (
                  <tr key={j.join_id} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-2 font-mono text-xs">{j.join_id}</td>
                    <td className="px-3 py-2 text-xs">
                      <span className="font-mono">{j.left_entity_id}</span>
                      <span className="mx-1 text-muted-foreground">→</span>
                      <span className="font-mono">{j.right_entity_id}</span>
                    </td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-rose-50 px-1.5 py-0.5 text-xs text-rose-700">
                        {j.join_type} ({j.relationship_type})
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground max-w-[300px] truncate">
                      {j.join_condition}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {j.allowed_for_ai ? (
                        <span className="text-green-600 text-xs">Yes</span>
                      ) : (
                        <span className="text-red-600 text-xs font-medium">No</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-xs tabular-nums ${j.fanout_risk_score >= 0.7 ? 'text-red-600 font-medium' : 'text-muted-foreground'}`}>
                        {j.fanout_risk_score.toFixed(2)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {joins.length === 0 && (
              <div className="py-8 text-center text-muted-foreground text-sm">등록된 조인 계약이 없습니다</div>
            )}
          </div>
        )}

        {(activeTab === 'entities' || activeTab === 'grains') && (
          <div className="py-12 text-center text-muted-foreground">
            <p className="text-sm">{activeTab === 'entities' ? '엔티티' : '그레인'} 뷰 — 구현 예정</p>
          </div>
        )}
      </div>
    </div>
  );
}
