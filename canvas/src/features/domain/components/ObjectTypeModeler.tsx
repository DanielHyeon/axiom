/**
 * ObjectTypeModeler — 메인 도메인 모델러 페이지 컴포넌트
 *
 * 3컬럼 레이아웃:
 *   좌측: ObjectType 목록 사이드바 (ObjectTypeList)
 *   중앙: 선택된 ObjectType 상세 (ObjectTypeDetail) 또는 빈 상태
 *   우측: 도메인 그래프 뷰어 (DomainGraphViewer) — 접기 가능
 *
 * KAIR ObjectTypeModeler.vue의 전체 레이아웃을 React로 재구현.
 */

import React, { useCallback, useMemo } from 'react';
import { Database, MousePointerClick } from 'lucide-react';
import { ObjectTypeList } from './ObjectTypeList';
import { ObjectTypeDetail } from './ObjectTypeDetail';
import { DomainGraphViewer } from './DomainGraphViewer';
import { CreateObjectTypeDialog } from './CreateObjectTypeDialog';
import { BehaviorEditor } from './BehaviorEditor';
import { useObjectTypeList, useUpdateObjectType } from '../hooks/useObjectTypes';
import { useDomainGraph } from '../hooks/useDomainGraph';
import { useDomainStore } from '../store/useDomainStore';
import type { ObjectType, Behavior } from '../types/domain';

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const ObjectTypeModeler: React.FC = () => {
  // ── 데이터 ──
  const { data, isLoading, refetch } = useObjectTypeList();
  const objectTypes = data?.objectTypes ?? [];
  const graphData = useDomainGraph(objectTypes);

  // ── 스토어 ──
  const {
    selectedObjectTypeId,
    selectObjectType,
    isCreateDialogOpen,
    closeCreateDialog,
    behaviorEditorState,
    closeBehaviorEditor,
    isGraphPanelCollapsed,
    toggleGraphPanel,
  } = useDomainStore();

  // ── 뮤테이션 ──
  const updateMutation = useUpdateObjectType();

  // 선택된 ObjectType 찾기
  const selectedOt = useMemo(
    () => objectTypes.find((ot) => ot.id === selectedObjectTypeId) ?? null,
    [objectTypes, selectedObjectTypeId],
  );

  // ObjectType 삭제 핸들러
  const handleDelete = useCallback(
    (ot: ObjectType) => {
      // ObjectTypeDetail에 AlertDialog가 있으므로 선택만 한다
      selectObjectType(ot.id);
    },
    [selectObjectType],
  );

  // 그래프 노드 클릭 → ObjectType 선택
  const handleGraphNodeClick = useCallback(
    (nodeId: string) => {
      selectObjectType(nodeId);
    },
    [selectObjectType],
  );

  // Behavior 저장 핸들러
  const handleBehaviorSave = useCallback(
    async (behaviorData: Omit<Behavior, 'id'>) => {
      const { objectTypeId, behaviorId, mode } = behaviorEditorState;
      if (!objectTypeId) return;

      const targetOt = objectTypes.find((ot) => ot.id === objectTypeId);
      if (!targetOt) return;

      let updatedBehaviors: Behavior[];

      if (mode === 'edit' && behaviorId) {
        // 기존 Behavior 수정
        updatedBehaviors = targetOt.behaviors.map((b) =>
          b.id === behaviorId ? { ...b, ...behaviorData } : b,
        );
      } else {
        // 새 Behavior 추가
        const newBehavior: Behavior = {
          id: `beh_${Date.now()}`,
          ...behaviorData,
        };
        updatedBehaviors = [...targetOt.behaviors, newBehavior];
      }

      await updateMutation.mutateAsync({
        id: objectTypeId,
        payload: { behaviors: updatedBehaviors },
      });

      closeBehaviorEditor();
    },
    [behaviorEditorState, objectTypes, updateMutation, closeBehaviorEditor],
  );

  // 편집 중인 Behavior 찾기
  const editingBehavior = useMemo(() => {
    if (!behaviorEditorState.open || !behaviorEditorState.objectTypeId) return null;
    const ot = objectTypes.find((o) => o.id === behaviorEditorState.objectTypeId);
    if (!ot || !behaviorEditorState.behaviorId) return null;
    return ot.behaviors.find((b) => b.id === behaviorEditorState.behaviorId) ?? null;
  }, [behaviorEditorState, objectTypes]);

  // 편집 중인 ObjectType의 컬럼 이름
  const editingColumns = useMemo(() => {
    if (!behaviorEditorState.objectTypeId) return [];
    const ot = objectTypes.find((o) => o.id === behaviorEditorState.objectTypeId);
    return ot?.fields.map((f) => f.name) ?? [];
  }, [behaviorEditorState.objectTypeId, objectTypes]);

  return (
    <div className="flex h-full overflow-hidden bg-background">
      {/* ── 좌측: ObjectType 목록 ── */}
      <ObjectTypeList
        objectTypes={objectTypes}
        isLoading={isLoading}
        onRefresh={() => refetch()}
        onDelete={handleDelete}
      />

      {/* ── 중앙: 상세 뷰 ── */}
      <main className="flex-1 min-w-0 overflow-hidden">
        {selectedOt ? (
          <ObjectTypeDetail
            objectType={selectedOt}
            allObjectTypes={objectTypes}
          />
        ) : (
          <EmptyState />
        )}
      </main>

      {/* ── 우측: 도메인 그래프 ── */}
      <DomainGraphViewer
        data={graphData}
        onNodeClick={handleGraphNodeClick}
        selectedNodeId={selectedObjectTypeId}
        collapsed={isGraphPanelCollapsed}
        onToggleCollapse={toggleGraphPanel}
        className={isGraphPanelCollapsed ? 'w-10' : 'w-80'}
      />

      {/* ── 생성 다이얼로그 ── */}
      <CreateObjectTypeDialog
        open={isCreateDialogOpen}
        onClose={closeCreateDialog}
        onCreated={() => refetch()}
      />

      {/* ── Behavior 편집기 ── */}
      <BehaviorEditor
        open={behaviorEditorState.open}
        onClose={closeBehaviorEditor}
        onSave={handleBehaviorSave}
        initialBehavior={editingBehavior}
        availableColumns={editingColumns}
        isSaving={updateMutation.isPending}
      />
    </div>
  );
};

// ──────────────────────────────────────
// 빈 상태 컴포넌트
// ──────────────────────────────────────

const EmptyState: React.FC = () => (
  <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
    <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-muted/50">
      <MousePointerClick className="h-8 w-8" />
    </div>
    <div className="text-center">
      <p className="text-sm font-medium">ObjectType을 선택하세요</p>
      <p className="text-xs mt-1">
        좌측 목록에서 ObjectType을 클릭하거나 그래프의 노드를 클릭합니다.
      </p>
    </div>
  </div>
);
