/**
 * 시멘틱 카탈로그 페이지 — .pen 디자인 사양 기반 리라이트
 *
 * 레이아웃: 수직
 *   - PageTabHeader (MainLayout에서 제공)
 *   - 11개 서브탭 바 (콘텐츠 영역 내부)
 *   - 검색바 + 액션 버튼
 *   - 테이블/패널 (탭별 분기)
 *
 * 디자인 사양:
 *   - 탭: Geist 12px semibold, 활성탭은 primary 하단 border 2px
 *   - 본문: 24px 패딩, 32px 좌우, 16px 갭
 *   - 테이블: 흰색 카드, 8px radius, 컬럼 사양 준수
 */
import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, Plus, Loader2, Inbox } from 'lucide-react';
import {
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
  useRelations,
  useCreateRelation,
  useDeleteRelation,
  useRules,
  useCreateRule,
  useDeleteRule,
  usePolicies,
  useCreatePolicy,
  useDeletePolicy,
  useTogglePolicyActive,
  useAliasGroups,
  useCreateAliasGroup,
  useExpansionRules,
  useActivateRule,
  useDeprecateRule,
  useSegments,
  useTimeContracts,
  useAccessPolicies,
} from '@/features/semantic-catalog/hooks/useSemanticCatalog';
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

// ── 탭 정의 ──
type TabKey =
  | 'concepts' | 'entities' | 'measures' | 'dimensions' | 'joins' | 'grains'
  | 'runtime' | 'relations' | 'rules' | 'aliases' | 'l2-extended';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'concepts', label: 'Concepts' },
  { key: 'entities', label: 'Entities' },
  { key: 'measures', label: 'Measures' },
  { key: 'dimensions', label: 'Dimensions' },
  { key: 'joins', label: 'Joins' },
  { key: 'grains', label: 'Grain' },
  { key: 'runtime', label: 'Runtime' },
  { key: 'relations', label: 'Relations' },
  { key: 'rules', label: 'Rules' },
  { key: 'aliases', label: 'Aliases' },
  { key: 'l2-extended', label: 'L2 Ext' },
];

// ── 탭별 검색 placeholder 및 버튼 텍스트 ──
const TAB_META: Partial<Record<TabKey, { placeholder: string; btnLabel?: string }>> = {
  concepts: { placeholder: 'Search concepts...', btnLabel: 'New Concept' },
  entities: { placeholder: 'Search entities...' },
  measures: { placeholder: 'Search measures...' },
  dimensions: { placeholder: 'Search dimensions...' },
  joins: { placeholder: 'Search joins...' },
  grains: { placeholder: 'Search grains...' },
  relations: { placeholder: 'Search relations...' },
  rules: { placeholder: 'Search rules...' },
  aliases: { placeholder: 'Search aliases...' },
};

export function SemanticCatalogPage() {
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('case_id') || undefined;

  const [activeTab, setActiveTab] = useState<TabKey>('concepts');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAliasGroupId, setSelectedAliasGroupId] = useState<string | undefined>();

  // ── 데이터 조회 ──
  const { isLoading: catalogLoading } = useSemanticCatalog(caseId);
  const { data: concepts = [] } = useConcepts({ case_id: caseId });
  const { data: entities = [] } = useEntities({ case_id: caseId });
  const { data: measures = [] } = useMeasures({ case_id: caseId });
  const { data: dimensions = [] } = useDimensions({ case_id: caseId });
  const { data: joins = [] } = useJoins({ case_id: caseId });
  const { data: grains = [] } = useGrains({ case_id: caseId });
  const { data: releases = [], isLoading: releasesLoading } = useReleases({ limit: 50 });

  // 관계
  const { data: relations = [] } = useRelations();
  const createRelationMutation = useCreateRelation();
  const deleteRelationMutation = useDeleteRelation();

  // 규칙/정책
  const { data: rules = [] } = useRules();
  const createRuleMutation = useCreateRule();
  const deleteRuleMutation = useDeleteRule();
  const { data: policies = [] } = usePolicies();
  const createPolicyMutation = useCreatePolicy();
  const deletePolicyMutation = useDeletePolicy();
  const togglePolicyMutation = useTogglePolicyActive();

  // 별칭
  const { data: aliasGroups = [] } = useAliasGroups();
  const createAliasGroupMutation = useCreateAliasGroup();
  const { data: expansionRules = [] } = useExpansionRules(selectedAliasGroupId);
  const activateRuleMutation = useActivateRule();
  const deprecateRuleMutation = useDeprecateRule();

  // L2 확장
  const { data: segments = [] } = useSegments();
  const { data: timeContracts = [] } = useTimeContracts();
  const { data: accessPolicies = [] } = useAccessPolicies();

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

  // ── 초기 로딩 ──
  if (catalogLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const meta = TAB_META[activeTab];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── 서브탭 바 — 11탭, 콘텐츠 영역 내부 ── */}
      <div className="shrink-0 flex items-center gap-0 px-8 border-b border-border overflow-x-auto scrollbar-none">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => {
              setActiveTab(tab.key);
              setSearchQuery('');
            }}
            className={[
              'shrink-0 px-3 py-2.5 text-xs font-semibold transition-colors border-b-2 whitespace-nowrap',
              activeTab === tab.key
                ? 'text-primary border-primary'
                : 'text-muted-foreground border-transparent hover:text-foreground',
            ].join(' ')}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── 본문 ── */}
      <div className="flex-1 flex flex-col gap-4 py-6 px-8 overflow-y-auto min-h-0">
        {/* 검색 + 액션 버튼 */}
        {meta && (
          <div className="flex items-center gap-3">
            {/* 검색 입력 */}
            <div className="flex items-center gap-2 h-9 w-[300px] rounded-md border border-border bg-white px-3">
              <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={meta.placeholder}
                className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground"
              />
            </div>

            {/* 액션 버튼 */}
            {meta.btnLabel && (
              <button
                type="button"
                className="flex items-center gap-1.5 h-9 rounded-md bg-primary px-3.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                {meta.btnLabel}
              </button>
            )}
          </div>
        )}

        {/* ── 탭 컨텐츠 ── */}
        <div className="flex-1 min-h-0">
          {activeTab === 'concepts' && (
            <ConceptsTableView
              concepts={concepts}
              searchQuery={searchQuery}
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
            <DimensionsTableView dimensions={dimensions} searchQuery={searchQuery} />
          )}

          {activeTab === 'joins' && (
            <JoinsTableView joins={joins} searchQuery={searchQuery} />
          )}

          {activeTab === 'grains' && <GrainTable grains={grains} />}

          {activeTab === 'runtime' && (
            <RuntimePanel releases={releases} isLoading={releasesLoading} />
          )}

          {activeTab === 'relations' && (
            <RelationTable
              relations={relations}
              onCreate={(data) => createRelationMutation.mutate(data)}
              onDelete={(id) => deleteRelationMutation.mutate(id)}
              isCreating={createRelationMutation.isPending}
              isDeleting={deleteRelationMutation.isPending}
            />
          )}

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

          {activeTab === 'l2-extended' && (
            <L2ExtendedPanel
              segments={segments}
              timeContracts={timeContracts}
              accessPolicies={accessPolicies}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Concepts 전용 테이블 뷰 (.pen 디자인 사양) ──

import type { OntologyConcept } from '@/features/semantic-catalog/types/semantic';

interface ConceptsTableViewProps {
  concepts: OntologyConcept[];
  searchQuery: string;
  onStatusChange: (conceptId: string, newStatus: ConceptStatus) => void;
  isStatusChanging: boolean;
}

function ConceptsTableView({ concepts, searchQuery, onStatusChange, isStatusChanging }: ConceptsTableViewProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // 검색 필터링
  const filtered = searchQuery
    ? concepts.filter((c) => {
        const q = searchQuery.toLowerCase();
        return (
          c.name_ko.toLowerCase().includes(q) ||
          (c.name_en?.toLowerCase().includes(q) ?? false) ||
          c.domain_id.toLowerCase().includes(q)
        );
      })
    : concepts;

  if (filtered.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
        <Inbox className="h-10 w-10" />
        <p className="text-sm">등록된 개념이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-white border border-border overflow-hidden">
      {/* 컬럼 헤더 */}
      <div className="flex items-center h-9 px-4 bg-muted/50">
        <span className="flex-1 text-[11px] font-semibold text-muted-foreground">Name</span>
        <span className="w-[120px] text-[11px] font-semibold text-muted-foreground">Domain</span>
        <span className="w-[100px] text-[11px] font-semibold text-muted-foreground">Status</span>
        <span className="w-[80px] text-[11px] font-semibold text-muted-foreground">Terms</span>
        <span className="w-[80px] text-[11px] font-semibold text-muted-foreground">Scope</span>
      </div>

      {/* 행 */}
      {filtered.map((c) => {
        const isExpanded = expandedId === c.concept_id;
        return (
          <div key={c.concept_id}>
            <button
              type="button"
              onClick={() => setExpandedId(isExpanded ? null : c.concept_id)}
              className="flex items-center w-full h-11 px-4 border-b border-border last:border-b-0 hover:bg-muted/20 transition-colors text-left"
            >
              <span className="flex-1 text-xs text-foreground truncate">
                {c.name_ko}
              </span>
              <span className="w-[120px] text-xs text-muted-foreground truncate">
                {c.domain_id}
              </span>
              <span className="w-[100px]">
                <StatusBadge status={c.status} />
              </span>
              <span className="w-[80px] text-xs text-foreground text-center">
                {c.terms?.length ?? 0}
              </span>
              <span className="w-[80px] text-xs text-blue-500 font-medium">
                Global
              </span>
            </button>
            {/* 확장 영역: 비즈니스 정의 + 상태 전이 */}
            {isExpanded && (
              <div className="px-6 py-3 bg-muted/10 border-b border-border space-y-2">
                {c.business_definition && (
                  <p className="text-xs text-muted-foreground">{c.business_definition}</p>
                )}
                {c.status === 'draft' && (
                  <button
                    type="button"
                    className="text-[10px] px-2 py-1 rounded bg-yellow-100 hover:bg-yellow-200 text-yellow-800"
                    disabled={isStatusChanging}
                    onClick={() => onStatusChange(c.concept_id, 'review')}
                  >
                    검토 요청
                  </button>
                )}
                {c.status === 'review' && (
                  <button
                    type="button"
                    className="text-[10px] px-2 py-1 rounded bg-green-100 hover:bg-green-200 text-green-800"
                    disabled={isStatusChanging}
                    onClick={() => onStatusChange(c.concept_id, 'approved')}
                  >
                    승인
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Dimensions 테이블 뷰 ──

import type { SemanticDimension } from '@/features/semantic-catalog/types/semantic';

interface DimensionsTableViewProps {
  dimensions: SemanticDimension[];
  searchQuery: string;
}

function DimensionsTableView({ dimensions, searchQuery }: DimensionsTableViewProps) {
  const filtered = searchQuery
    ? dimensions.filter((d) => d.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : dimensions;

  if (filtered.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
        <Inbox className="h-10 w-10" />
        <p className="text-sm">등록된 차원이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-white border border-border overflow-hidden">
      <div className="flex items-center h-9 px-4 bg-muted/50">
        <span className="flex-1 text-[11px] font-semibold text-muted-foreground">Name</span>
        <span className="w-[120px] text-[11px] font-semibold text-muted-foreground">Type</span>
        <span className="w-[200px] text-[11px] font-semibold text-muted-foreground">SQL Expression</span>
        <span className="w-[120px] text-[11px] font-semibold text-muted-foreground">Hierarchy</span>
        <span className="w-[100px] text-[11px] font-semibold text-muted-foreground">Status</span>
      </div>
      {filtered.map((d) => (
        <div
          key={d.dimension_id}
          className="flex items-center h-11 px-4 border-b border-border last:border-b-0 hover:bg-muted/20 transition-colors"
        >
          <span className="flex-1 text-xs font-medium text-foreground truncate">{d.name}</span>
          <span className="w-[120px]">
            <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700">{d.value_type}</span>
          </span>
          <span className="w-[200px] text-[10px] font-mono text-muted-foreground truncate">{d.sql_expression}</span>
          <span className="w-[120px] text-[10px] text-muted-foreground truncate">{d.hierarchy_path || '—'}</span>
          <span className="w-[100px]">
            <StatusBadge status={d.status} />
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Joins 테이블 뷰 ──

import type { JoinContract } from '@/features/semantic-catalog/types/semantic';

interface JoinsTableViewProps {
  joins: JoinContract[];
  searchQuery: string;
}

function JoinsTableView({ joins, searchQuery }: JoinsTableViewProps) {
  const filtered = searchQuery
    ? joins.filter(
        (j) =>
          j.left_entity_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
          j.right_entity_id.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : joins;

  if (filtered.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
        <Inbox className="h-10 w-10" />
        <p className="text-sm">등록된 조인 계약이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-white border border-border overflow-hidden">
      <div className="flex items-center h-9 px-4 bg-muted/50">
        <span className="flex-1 text-[11px] font-semibold text-muted-foreground">Left → Right</span>
        <span className="w-[120px] text-[11px] font-semibold text-muted-foreground">Type</span>
        <span className="w-[200px] text-[11px] font-semibold text-muted-foreground">Condition</span>
        <span className="w-[80px] text-center text-[11px] font-semibold text-muted-foreground">AI</span>
        <span className="w-[80px] text-center text-[11px] font-semibold text-muted-foreground">Fanout</span>
      </div>
      {filtered.map((j) => (
        <div
          key={j.join_id}
          className="flex items-center h-11 px-4 border-b border-border last:border-b-0 hover:bg-muted/20 transition-colors"
        >
          <span className="flex-1 text-[10px] font-mono text-foreground truncate">
            {j.left_entity_id} <span className="text-muted-foreground mx-1">→</span> {j.right_entity_id}
          </span>
          <span className="w-[120px]">
            <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] text-rose-700">
              {j.join_type} ({j.relationship_type})
            </span>
          </span>
          <span className="w-[200px] text-[10px] font-mono text-muted-foreground truncate">{j.join_condition}</span>
          <span className="w-[80px] text-center">
            {j.allowed_for_ai ? (
              <span className="text-green-600 text-[10px]">Yes</span>
            ) : (
              <span className="text-red-600 text-[10px] font-medium">No</span>
            )}
          </span>
          <span className="w-[80px] text-center">
            <span
              className={`text-[10px] tabular-nums ${j.fanout_risk_score >= 0.7 ? 'text-red-600 font-medium' : 'text-muted-foreground'}`}
            >
              {j.fanout_risk_score.toFixed(2)}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}
