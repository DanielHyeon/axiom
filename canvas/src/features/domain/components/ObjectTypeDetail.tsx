/**
 * ObjectTypeDetail — ObjectType 상세 뷰
 *
 * 중앙 패널: 속성(필드), 관계, Behavior, 차트 설정, 온톨로지 매핑을
 * 탭으로 구분하여 표시한다.
 * KAIR의 ObjectTypeModeler 중앙+상세 영역을 React + Tailwind로 재구현.
 */

import React, { useCallback, useMemo, useState } from 'react';
import {
  Database,
  Pencil,
  Trash2,
  Save,
  X,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { FieldEditor } from './FieldEditor';
import { RelationEditor } from './RelationEditor';
import { BehaviorPanel } from './BehaviorPanel';
import { ChartConfigPanel } from './ChartConfigPanel';
import { OntologyMappingPanel } from './OntologyMappingPanel';
import { useUpdateObjectType, useDeleteObjectType } from '../hooks/useObjectTypes';
import { useDomainStore } from '../store/useDomainStore';
import type { ObjectType, ObjectTypeField, ObjectTypeRelation, ChartConfig, Behavior } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface ObjectTypeDetailProps {
  objectType: ObjectType;
  allObjectTypes: ObjectType[];
}

// ──────────────────────────────────────
// 탭 목록
// ──────────────────────────────────────

type DetailTab = 'fields' | 'relations' | 'behaviors' | 'chart' | 'ontology';

const TAB_ITEMS: { key: DetailTab; label: (ot: ObjectType) => string }[] = [
  { key: 'fields', label: (ot) => `필드 (${ot.fields.length})` },
  { key: 'relations', label: (ot) => `관계 (${ot.relations.length})` },
  { key: 'behaviors', label: (ot) => `Behaviors (${ot.behaviors.length})` },
  { key: 'chart', label: () => '차트' },
  { key: 'ontology', label: () => '온톨로지' },
];

// ──────────────────────────────────────
// 상태 뱃지 색상
// ──────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  draft: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  deprecated: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
};

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const ObjectTypeDetail: React.FC<ObjectTypeDetailProps> = ({
  objectType,
  allObjectTypes,
}) => {
  const { openBehaviorEditor, selectObjectType } = useDomainStore();
  const updateMutation = useUpdateObjectType();
  const deleteMutation = useDeleteObjectType();

  // 탭
  const [activeTab, setActiveTab] = useState<DetailTab>('fields');

  // 편집 모드 상태
  const [isEditing, setIsEditing] = useState(false);
  const [editFields, setEditFields] = useState<ObjectTypeField[]>([]);
  const [editRelations, setEditRelations] = useState<ObjectTypeRelation[]>([]);
  const [editChartConfig, setEditChartConfig] = useState<ChartConfig>({ chartType: 'none' });

  // 삭제 확인
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // 편집 시작
  const startEdit = useCallback(() => {
    setEditFields([...objectType.fields]);
    setEditRelations([...objectType.relations]);
    setEditChartConfig(objectType.chartConfig ?? { chartType: 'none' });
    setIsEditing(true);
  }, [objectType]);

  // 편집 취소
  const cancelEdit = useCallback(() => {
    setIsEditing(false);
  }, []);

  // 편집 저장
  const saveEdit = useCallback(async () => {
    try {
      await updateMutation.mutateAsync({
        id: objectType.id,
        payload: {
          fields: editFields,
          relations: editRelations,
          chartConfig: editChartConfig,
        },
      });
      setIsEditing(false);
    } catch {
      // 에러는 mutation에서 처리
    }
  }, [objectType.id, editFields, editRelations, editChartConfig, updateMutation]);

  // 삭제
  const handleDelete = useCallback(async () => {
    try {
      await deleteMutation.mutateAsync(objectType.id);
      selectObjectType(null);
    } catch {
      // 에러는 mutation에서 처리
    }
  }, [objectType.id, deleteMutation, selectObjectType]);

  // 관계 편집용 타겟 목록 (자기 자신 제외)
  const availableTargets = useMemo(
    () => allObjectTypes.filter((ot) => ot.id !== objectType.id),
    [allObjectTypes, objectType.id],
  );

  const isSaving = updateMutation.isPending;
  const isDeleting = deleteMutation.isPending;

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-card">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/10 text-primary">
            <Database className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">
              {objectType.displayName || objectType.name}
            </h2>
            <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
              <span>{objectType.name}</span>
              <Badge variant="outline" className={STATUS_STYLES[objectType.status]}>
                {objectType.status}
              </Badge>
              {objectType.sourceTable && (
                <span className="text-muted-foreground/60">
                  {objectType.sourceSchema}.{objectType.sourceTable}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 액션 버튼 */}
        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button variant="ghost" size="sm" onClick={cancelEdit} disabled={isSaving}>
                <X className="h-3.5 w-3.5 mr-1" />
                취소
              </Button>
              <Button size="sm" onClick={saveEdit} disabled={isSaving}>
                {isSaving ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5 mr-1" />
                )}
                저장
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={startEdit}>
                <Pencil className="h-3.5 w-3.5 mr-1" />
                편집
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isDeleting}
              >
                {isDeleting ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5 mr-1" />
                )}
                삭제
              </Button>
            </>
          )}
        </div>
      </div>

      {/* 탭 네비게이션 */}
      <div className="flex border-b border-border px-5 bg-card">
        {TAB_ITEMS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-px',
              activeTab === tab.key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label(objectType)}
          </button>
        ))}
      </div>

      {/* 탭 콘텐츠 */}
      <div className="flex-1 overflow-y-auto p-5">
        {activeTab === 'fields' && (
          <FieldEditor
            fields={isEditing ? editFields : objectType.fields}
            onChange={setEditFields}
            readOnly={!isEditing}
          />
        )}

        {activeTab === 'relations' && (
          <RelationEditor
            relations={isEditing ? editRelations : objectType.relations}
            onChange={setEditRelations}
            availableTargets={availableTargets}
            readOnly={!isEditing}
          />
        )}

        {activeTab === 'behaviors' && (
          <BehaviorPanel
            behaviors={objectType.behaviors}
            onAdd={() => openBehaviorEditor(objectType.id, null, 'create')}
            onEdit={(b) => openBehaviorEditor(objectType.id, b.id, 'edit')}
            onExecute={(b) => {
              console.log('[ObjectTypeDetail] Behavior 실행:', b.name);
            }}
            readOnly={false}
          />
        )}

        {activeTab === 'chart' && (
          <ChartConfigPanel
            config={isEditing ? editChartConfig : objectType.chartConfig ?? { chartType: 'none' }}
            onChange={setEditChartConfig}
            fields={objectType.fields}
            readOnly={!isEditing}
          />
        )}

        {activeTab === 'ontology' && (
          <OntologyMappingPanel objectType={objectType} />
        )}
      </div>

      {/* 삭제 확인 다이얼로그 */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-card border border-border rounded-lg w-[420px] shadow-xl">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              <h3 className="text-sm font-semibold text-foreground">ObjectType 삭제</h3>
            </div>
            <div className="px-5 py-4">
              <p className="text-sm text-foreground">
                <strong className="text-destructive">{objectType.displayName || objectType.name}</strong>을(를) 삭제하시겠습니까?
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                이 작업은 되돌릴 수 없습니다. 관련된 Materialized View와 Behavior도 함께 삭제됩니다.
              </p>
            </div>
            <div className="flex justify-end gap-2 px-5 py-3 border-t border-border">
              <Button variant="ghost" size="sm" onClick={() => setShowDeleteConfirm(false)}>
                취소
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => { handleDelete(); setShowDeleteConfirm(false); }}
                disabled={isDeleting}
              >
                {isDeleting && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
                삭제
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
