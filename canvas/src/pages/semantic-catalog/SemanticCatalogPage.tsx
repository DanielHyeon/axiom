/**
 * 시멘틱 카탈로그 페이지 — 11탭 브라우저
 *
 * 개념/엔티티/지표/차원/조인/그레인/런타임/관계/규칙·정책/별칭/L2확장
 * Control Plane에서 정의한 시멘틱 계약을 조회하고 관리한다.
 * 개념 상태 전이(draft->review->approved), 지표 컴파일, 배포 등을 지원.
 */
import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2, BookOpen } from 'lucide-react';
import {
import { useTranslation } from 'react-i18next';
  useSemanticCatalog,
  useConcepts,
  useEntities,
  useMeasures,
  useDimensions,
  useJoins,
  useGrains,
  useReleases,
  useChangeConceptStatus,
  useCompileMeasure,
  usePublish,
  // 관계
  useRelations,
  useCreateRelation,
  useDeleteRelation,
  // 규칙/정책
  useRules,
  useCreateRule,
  useDeleteRule,
  usePolicies,
  useCreatePolicy,
  useDeletePolicy,
  useTogglePolicyActive,
  // 별칭
  useAliasGroups,
  useCreateAliasGroup,
  useExpansionRules,
  useActivateRule,
  useDeprecateRule,
  // L2 확장
  useSegments,
  useTimeContracts,
  useAccessPolicies,
} from '@/features/semantic-catalog/hooks/useSemanticCatalog';
import { CatalogSummaryCards } from '@/features/semantic-catalog/components/CatalogSummaryCards';
import { ConceptTable } from '@/features/semantic-catalog/components/ConceptTable';
import { EntityTable } from '@/features/semantic-catalog/components/EntityTable';
import { MeasureTable } from '@/features/semantic-catalog/components/MeasureTable';
import { GrainTable } from '@/features/semantic-catalog/components/GrainTable';
import { RuntimePanel } from '@/features/semantic-catalog/components/RuntimePanel';
import { RelationTable } from '@/features/semantic-catalog/components/RelationTable';
import { RulePolicyPanel } from '@/features/semantic-catalog/components/RulePolicyPanel';
import { AliasPanel } from '@/features/semantic-catalog/components/AliasPanel';
import { L2ExtendedPanel } from '@/features/semantic-catalog/components/L2ExtendedPanel';
import { StatusBadge } from '@/features/semantic-catalog/components/StatusBadge';
import type { ConceptStatus, CompileResult } from '@/features/semantic-catalog/types/semantic';

type TabKey =
  | 'concepts' | 'entities' | 'measures' | 'dimensions' | 'joins' | 'grains' | 'runtime'
  | 'relations' | 'rules' | 'aliases' | 'l2-extended';

export function SemanticCatalogPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('case_id') || undefined;

  const [activeTab, setActiveTab] = useState<TabKey>('concepts');

  // ── 별칭 탭 상태 ──
  const [selectedAliasGroupId, setSelectedAliasGroupId] = useState<string | undefined>();

  // ── 기존 데이터 조회 ──
  const { data: catalog, isLoading: catalogLoading } = useSemanticCatalog(caseId);
  const { data: concepts = [] } = useConcepts({ case_id: caseId });
  const { data: entities = [] } = useEntities({ case_id: caseId });
  const { data: measures = [] } = useMeasures({ case_id: caseId });
  const { data: dimensions = [] } = useDimensions({ case_id: caseId });
  const { data: joins = [] } = useJoins({ case_id: caseId });
  const { data: grains = [] } = useGrains({ case_id: caseId });
  const { data: releases = [], isLoading: releasesLoading } = useReleases({ limit: 50 });

  // ── 관계 데이터 ──
  const { data: relations = [] } = useRelations();
  const createRelationMutation = useCreateRelation();
  const deleteRelationMutation = useDeleteRelation();

  // ── 규칙/정책 데이터 ──
  const { data: rules = [] } = useRules();
  const createRuleMutation = useCreateRule();
  const deleteRuleMutation = useDeleteRule();
  const { data: policies = [] } = usePolicies();
  const createPolicyMutation = useCreatePolicy();
  const deletePolicyMutation = useDeletePolicy();
  const togglePolicyMutation = useTogglePolicyActive();

  // ── 별칭 데이터 ──
  const { data: aliasGroups = [] } = useAliasGroups();
  const createAliasGroupMutation = useCreateAliasGroup();
  const { data: expansionRules = [] } = useExpansionRules(selectedAliasGroupId);
  const activateRuleMutation = useActivateRule();
  const deprecateRuleMutation = useDeprecateRule();

  // ── L2 확장 데이터 ──
  const { data: segments = [] } = useSegments();
  const { data: timeContracts = [] } = useTimeContracts();
  const { data: accessPolicies = [] } = useAccessPolicies();

  // ── 기존 뮤테이션 ──
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

  const handlePublishMeasure = useCallback(
    (measureId: string) => {
      publishMutation.mutate({ objectType: 'measure', objectId: measureId });
    },
    [publishMutation],
  );

  const handlePublishEntity = useCallback(
    (entityId: string) => {
      publishMutation.mutate({ objectType: 'entity', objectId: entityId });
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

  // CatalogSummary에 없는 탭의 카운트
  const extraCounts: Record<string, number> = {
    runtime: releases.length,
    relations: relations.length,
    rules: rules.length + policies.length,
    aliases: aliasGroups.length,
    'l2-extended': segments.length + timeContracts.length + accessPolicies.length,
  };

  return (
    <div className="flex flex-col gap-4 p-4 h-full overflow-auto">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <BookOpen className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-xl font-bold">{t('sidebar.semanticCatalog')}</h1>
          <p className="text-sm text-muted-foreground">
            {t('semanticCatalogPage.m36cf6869')}
          </p>
        </div>
      </div>

      {/* 요약 카드 (11탭) */}
      <CatalogSummaryCards
        summary={summary}
        activeTab={activeTab}
        onTabChange={(t) => setActiveTab(t as TabKey)}
        extraCounts={extraCounts}
      />

      {/* 탭별 내용 */}
      <div className="flex-1 min-h-0">
        {activeTab === 'concepts' && (
          <ConceptTable
            concepts={concepts}
            onStatusChange={handleStatusChange}
            isStatusChanging={statusMutation.isPending}
          />
        )}

        {activeTab === 'entities' && (
          <EntityTable
            entities={entities}
            onPublish={handlePublishEntity}
            isPublishing={publishMutation.isPending}
          />
        )}

        {activeTab === 'measures' && (
          <MeasureTable
            measures={measures}
            onCompile={handleCompile}
            onPublish={handlePublishMeasure}
            isPublishing={publishMutation.isPending}
          />
        )}

        {activeTab === 'dimensions' && (
          <div className="rounded-lg border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogPage.msgc2d743e6')}</th>
                  <th className="px-3 py-2 text-left font-medium">{t('mvExt.colName')}</th>
                  <th className="px-3 py-2 text-left font-medium">{t('objectExplorerExt.typeLabel')}</th>
                  <th className="px-3 py-2 text-left font-medium">{t('dataQualityExt.sqlExpression')}</th>
                  <th className="px-3 py-2 text-left font-medium">{t('olapStudioExt.hierarchy')}</th>
                  <th className="px-3 py-2 text-left font-medium">{t('dataQualityExt.incidentCols.status')}</th>
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
              <div className="py-8 text-center text-muted-foreground text-sm">{t('semanticCatalogExt.noDimensions')}</div>
            )}
          </div>
        )}

        {activeTab === 'joins' && (
          <div className="rounded-lg border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.joinId')}</th>
                  <th className="px-3 py-2 text-left font-medium">Left → Right</th>
                  <th className="px-3 py-2 text-left font-medium">{t('objectExplorerExt.typeLabel')}</th>
                  <th className="px-3 py-2 text-left font-medium">{t('cepExt.colCondition')}</th>
                  <th className="px-3 py-2 text-center font-medium">{t('semanticCatalogExt.aiAllowed')}</th>
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
              <div className="py-8 text-center text-muted-foreground text-sm">{t('semanticCatalogExt.noJoinContracts')}</div>
            )}
          </div>
        )}

        {activeTab === 'grains' && (
          <GrainTable grains={grains} />
        )}

        {activeTab === 'runtime' && (
          <RuntimePanel releases={releases} isLoading={releasesLoading} />
        )}

        {/* ── 관계 탭 ── */}
        {activeTab === 'relations' && (
          <RelationTable
            relations={relations}
            onCreate={(data) => createRelationMutation.mutate(data)}
            onDelete={(id) => deleteRelationMutation.mutate(id)}
            isCreating={createRelationMutation.isPending}
            isDeleting={deleteRelationMutation.isPending}
          />
        )}

        {/* ── 규칙/정책 탭 ── */}
        {activeTab === 'rules' && (
          <RulePolicyPanel
            rules={rules}
            policies={policies}
            onCreateRule={(data) => createRuleMutation.mutate(data)}
            onDeleteRule={(id) => deleteRuleMutation.mutate(id)}
            onCreatePolicy={(data) => createPolicyMutation.mutate(data)}
            onDeletePolicy={(id) => deletePolicyMutation.mutate(id)}
            onTogglePolicyActive={(id, isActive) => togglePolicyMutation.mutate({ id, isActive })}
            isCreatingRule={createRuleMutation.isPending}
            isCreatingPolicy={createPolicyMutation.isPending}
          />
        )}

        {/* ── 별칭 탭 ── */}
        {activeTab === 'aliases' && (
          <AliasPanel
            aliasGroups={aliasGroups}
            expansionRules={expansionRules}
            selectedGroupId={selectedAliasGroupId}
            onSelectGroup={setSelectedAliasGroupId}
            onCreateGroup={(data) => createAliasGroupMutation.mutate(data)}
            onActivateRule={(id) => activateRuleMutation.mutate(id)}
            onDeprecateRule={(id) => deprecateRuleMutation.mutate(id)}
            isCreatingGroup={createAliasGroupMutation.isPending}
          />
        )}

        {/* ── L2 확장 탭 ── */}
        {activeTab === 'l2-extended' && (
          <L2ExtendedPanel
            segments={segments}
            timeContracts={timeContracts}
            accessPolicies={accessPolicies}
          />
        )}
      </div>
    </div>
  );
}
