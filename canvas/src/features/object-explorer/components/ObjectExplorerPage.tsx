/**
 * ObjectExplorerPage — 오브젝트 탐색기 메인 페이지
 *
 * KAIR ObjectExplorerTab.vue를 Axiom React 패턴으로 이식한 3컬럼 레이아웃.
 * 좌측: ObjectTypeSelector (타입 목록)
 * 중앙: InstanceSearch + InstanceTable (인스턴스 목록)
 * 우측: InstanceDetail (선택된 인스턴스 상세)
 * 하단: InstanceGraph (관계 시각화)
 *
 * 도메인 feature의 ObjectType API를 재사용하고,
 * 인스턴스 데이터는 object-explorer API로 로딩한다.
 */

import React, { useCallback, useMemo } from 'react';
import { Search, PanelLeftClose, PanelLeftOpen, Network } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// 도메인 feature 재사용
import { useObjectTypeList } from '@/features/domain/hooks/useObjectTypes';

// 오브젝트 탐색기 로컬 훅/스토어
import { useObjectExplorerStore } from '../store/useObjectExplorerStore';
import { useObjectInstances } from '../hooks/useObjectInstances';
import { useInstanceDetail } from '../hooks/useInstanceDetail';

// 하위 컴포넌트
import { ObjectTypeSelector } from './ObjectTypeSelector';
import { InstanceSearch } from './InstanceSearch';
import { InstanceTable } from './InstanceTable';
import { InstanceDetail } from './InstanceDetail';
import { InstanceGraph } from './InstanceGraph';

import type { ObjectType, ObjectInstance } from '../types/object-explorer';

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const ObjectExplorerPage: React.FC = () => {
  // ── 스토어 ──
  const {
    selectedObjectTypeId,
    selectedInstanceId,
    filter,
    leftPanelTab,
    showGraphPanel,
    selectObjectType,
    selectInstance,
    setFilter,
    resetFilter,
    setLeftPanelTab,
    toggleGraphPanel,
    reset,
  } = useObjectExplorerStore();

  // ── ObjectType 목록 (도메인 feature 재사용) ──
  const { data: objectTypeListData, isLoading: isTypesLoading } = useObjectTypeList();
  const objectTypes = useMemo(
    () => objectTypeListData?.objectTypes ?? [],
    [objectTypeListData],
  );

  // 선택된 ObjectType 객체
  const selectedObjectType = useMemo(
    () => objectTypes.find((t) => t.id === selectedObjectTypeId) ?? null,
    [objectTypes, selectedObjectTypeId],
  );

  // ── 인스턴스 목록 ──
  const {
    data: instanceListData,
    isLoading: isInstancesLoading,
  } = useObjectInstances(selectedObjectTypeId, filter);

  const instances = instanceListData?.instances ?? [];
  const totalInstances = instanceListData?.total ?? 0;

  // ── 인스턴스 상세 ──
  const { data: instanceDetailData } = useInstanceDetail(selectedInstanceId);
  const selectedInstance = instanceDetailData?.instance ?? null;

  // 선택 중인 인스턴스 (상세 로딩 전에도 목록에서 매칭)
  const displayInstance = useMemo(() => {
    if (selectedInstance) return selectedInstance;
    if (selectedInstanceId) {
      return instances.find((i) => i.id === selectedInstanceId) ?? null;
    }
    return null;
  }, [selectedInstance, selectedInstanceId, instances]);

  // ── 핸들러 ──

  // ObjectType 선택
  const handleTypeSelect = useCallback(
    (ot: ObjectType) => {
      selectObjectType(ot.id);
    },
    [selectObjectType],
  );

  // 인스턴스 선택
  const handleInstanceSelect = useCallback(
    (inst: ObjectInstance) => {
      selectInstance(inst.id);
    },
    [selectInstance],
  );

  // 인스턴스 상세 닫기 → 검색 탭으로 복귀
  const handleDetailClose = useCallback(() => {
    selectInstance(null);
    setLeftPanelTab('search');
  }, [selectInstance, setLeftPanelTab]);

  // 검색 실행 (필터 변경 시 자동 반영되므로 별도 동작 없음)
  const handleSearch = useCallback(() => {
    // 페이지 1로 리셋 (이미 setFilter에서 처리됨)
  }, []);

  // 관련 인스턴스 클릭
  const handleRelatedClick = useCallback(
    (instanceId: string) => {
      selectInstance(instanceId);
    },
    [selectInstance],
  );

  // 전체 초기화
  const handleReset = useCallback(() => {
    reset();
  }, [reset]);

  // ── 좌측 패널 표시 여부 ──
  const showLeftPanel = leftPanelTab === 'search' || leftPanelTab === 'detail';

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* ─── 메인 3컬럼 레이아웃 ─── */}
      <div className="flex flex-1 min-h-0">
        {/* 좌측: ObjectType 선택 / 인스턴스 상세 */}
        <div className="w-[280px] shrink-0 border-r border-border bg-card flex flex-col">
          {/* 탭 헤더 */}
          <div className="flex border-b border-border bg-muted/30">
            <button
              className={cn(
                'flex-1 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors',
                leftPanelTab === 'search'
                  ? 'text-primary border-primary bg-card'
                  : 'text-muted-foreground border-transparent hover:text-foreground hover:bg-muted/50',
              )}
              onClick={() => setLeftPanelTab('search')}
            >
              검색
            </button>
            <button
              className={cn(
                'flex-1 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors',
                leftPanelTab === 'detail'
                  ? 'text-primary border-primary bg-card'
                  : 'text-muted-foreground border-transparent hover:text-foreground hover:bg-muted/50',
                !displayInstance && 'opacity-50 cursor-not-allowed',
              )}
              disabled={!displayInstance}
              onClick={() => displayInstance && setLeftPanelTab('detail')}
            >
              상세
            </button>
          </div>

          {/* 탭 콘텐츠 */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {leftPanelTab === 'search' && (
              <ObjectTypeSelector
                objectTypes={objectTypes}
                selectedId={selectedObjectTypeId}
                isLoading={isTypesLoading}
                onSelect={handleTypeSelect}
                onReset={handleReset}
              />
            )}

            {leftPanelTab === 'detail' && displayInstance && (
              <InstanceDetail
                instance={displayInstance}
                objectType={selectedObjectType}
                onClose={handleDetailClose}
                onRelatedClick={handleRelatedClick}
              />
            )}

            {leftPanelTab === 'detail' && !displayInstance && (
              <div className="flex items-center justify-center h-full text-muted-foreground text-xs">
                노드를 선택하면 상세 정보가 표시됩니다
              </div>
            )}
          </div>
        </div>

        {/* 중앙 + 우측: 인스턴스 테이블 + 그래프 */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* 검색 바 */}
          <InstanceSearch
            filter={filter}
            onFilterChange={setFilter}
            onSearch={handleSearch}
            objectTypeName={selectedObjectType?.displayName || selectedObjectType?.name}
          />

          {/* 인스턴스 테이블 */}
          <div className="flex-1 min-h-0">
            <InstanceTable
              objectType={selectedObjectType}
              instances={instances}
              total={totalInstances}
              filter={filter}
              onFilterChange={setFilter}
              selectedInstanceId={selectedInstanceId}
              onSelectInstance={handleInstanceSelect}
              isLoading={isInstancesLoading}
            />
          </div>

          {/* 하단: 관계 그래프 */}
          <InstanceGraph
            instance={displayInstance}
            onNodeClick={handleRelatedClick}
            collapsed={!showGraphPanel}
            onToggleCollapse={toggleGraphPanel}
            className={showGraphPanel ? 'h-[300px]' : ''}
          />
        </div>
      </div>
    </div>
  );
};
