/**
 * DomainModelerPage — .pen 디자인 사양 기반 리라이트
 *
 * 레이아웃: 수평 분할
 *   좌측 Tree Panel (260px, 우측 border, 16px 패딩, 8px 갭)
 *     - "Domain Hierarchy" Sora 12px semibold
 *     - 트리 노드: folder/box 아이콘, 들여쓰기된 자식
 *   우측 Model Canvas (fill, 빈 상태 — boxes 아이콘 + "Select a domain..." 텍스트)
 *
 * 백엔드 연동: Synapse /api/v3/synapse/domain/object-types
 * 도메인 트리는 ontology domains API 또는 object-types로 구성
 */
import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Folder, Box, Boxes, Loader2, AlertCircle, ChevronRight, ChevronDown } from 'lucide-react';
import { useObjectTypeList } from '@/features/domain/hooks/useObjectTypes';
import { ObjectTypeDetail } from '@/features/domain/components/ObjectTypeDetail';
import { CreateObjectTypeDialog } from '@/features/domain/components/CreateObjectTypeDialog';
import { BehaviorEditor } from '@/features/domain/components/BehaviorEditor';
import { useDomainStore } from '@/features/domain/store/useDomainStore';
import type { ObjectType, Behavior } from '@/features/domain/types/domain';
import { useUpdateObjectType } from '@/features/domain/hooks/useObjectTypes';

// ── 도메인 트리 노드 타입 ──
interface TreeNode {
  id: string;
  label: string;
  type: 'domain' | 'object';
  children?: TreeNode[];
  objectType?: ObjectType;
}

// ── ObjectType 목록 → 도메인 트리 변환 ──
function buildTree(objectTypes: ObjectType[]): TreeNode[] {
  // sourceSchema 또는 임의의 그룹핑 기준으로 도메인 폴더를 생성
  const domainMap = new Map<string, ObjectType[]>();

  for (const ot of objectTypes) {
    const domain = ot.sourceSchema || ot.sourceTable?.split('_')[0] || 'Default';
    if (!domainMap.has(domain)) domainMap.set(domain, []);
    domainMap.get(domain)!.push(ot);
  }

  // 도메인이 비어 있으면 하드코딩 예시 표시 (빈 상태 대신)
  if (domainMap.size === 0) {
    return [
      {
        id: 'manufacturing',
        label: 'Manufacturing',
        type: 'domain',
        children: [],
      },
      {
        id: 'supply-chain',
        label: 'Supply Chain',
        type: 'domain',
        children: [],
      },
    ];
  }

  return Array.from(domainMap.entries()).map(([domain, ots]) => ({
    id: `domain-${domain}`,
    label: domain.charAt(0).toUpperCase() + domain.slice(1),
    type: 'domain' as const,
    children: ots.map((ot) => ({
      id: ot.id,
      label: ot.displayName || ot.name,
      type: 'object' as const,
      objectType: ot,
    })),
  }));
}

export const DomainModelerPage: React.FC = () => {
  const { t } = useTranslation();

  // ── 데이터 ──
  const { data, isLoading, error, refetch } = useObjectTypeList();
  const objectTypes = useMemo(() => data?.objectTypes ?? [], [data]);
  const tree = buildTree(objectTypes);

  // ── 스토어 ──
  const {
    selectedObjectTypeId,
    selectObjectType,
    isCreateDialogOpen,
    closeCreateDialog,
    behaviorEditorState,
    closeBehaviorEditor,
  } = useDomainStore();

  // ── 뮤테이션 ──
  const updateMutation = useUpdateObjectType();

  // ── 선택된 ObjectType ──
  const selectedOt = objectTypes.find((ot) => ot.id === selectedObjectTypeId) ?? null;

  // ── 확장된 도메인 폴더 ──
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set());

  const toggleDomain = (domainId: string) => {
    setExpandedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(domainId)) next.delete(domainId);
      else next.add(domainId);
      return next;
    });
  };

  // ── Behavior 저장 핸들러 ──
  const handleBehaviorSave = async (behaviorData: Omit<Behavior, 'id'>) => {
    const { objectTypeId, behaviorId: editBehaviorId, mode } = behaviorEditorState;
    if (!objectTypeId) return;

    const targetOt = objectTypes.find((ot) => ot.id === objectTypeId);
    if (!targetOt) return;

    let updatedBehaviors: Behavior[];
    if (mode === 'edit' && editBehaviorId) {
      updatedBehaviors = targetOt.behaviors.map((b) =>
        b.id === editBehaviorId ? { ...b, ...behaviorData } : b,
      );
    } else {
      // crypto.randomUUID는 순수하지 않지만 이벤트 핸들러 내부이므로 안전
      const newId = crypto.randomUUID();
      const newBehavior: Behavior = { id: newId, ...behaviorData };
      updatedBehaviors = [...targetOt.behaviors, newBehavior];
    }

    await updateMutation.mutateAsync({
      id: objectTypeId,
      payload: { behaviors: updatedBehaviors },
    });
    closeBehaviorEditor();
  };

  // 편집 중인 Behavior
  const editingBehavior = (() => {
    if (!behaviorEditorState.open || !behaviorEditorState.objectTypeId) return null;
    const ot = objectTypes.find((o) => o.id === behaviorEditorState.objectTypeId);
    if (!ot || !behaviorEditorState.behaviorId) return null;
    return ot.behaviors.find((b) => b.id === behaviorEditorState.behaviorId) ?? null;
  })();

  const editingColumns = (() => {
    if (!behaviorEditorState.objectTypeId) return [];
    const ot = objectTypes.find((o) => o.id === behaviorEditorState.objectTypeId);
    return ot?.fields.map((f) => f.name) ?? [];
  })();

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── 좌측: Tree Panel (260px) ── */}
      <aside className="w-[260px] shrink-0 flex flex-col gap-2 p-3 border-r border-border overflow-y-auto">
        <h3 className="font-heading text-xs font-semibold text-foreground px-2 py-1">
          Domain Hierarchy
        </h3>

        {/* 로딩 */}
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* 에러 */}
        {error && !isLoading && (
          <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 mx-1">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>도메인을 불러올 수 없습니다.</span>
          </div>
        )}

        {/* 트리 렌더 */}
        {!isLoading && tree.map((node) => (
          <TreeNodeItem
            key={node.id}
            node={node}
            level={0}
            expandedDomains={expandedDomains}
            selectedId={selectedObjectTypeId}
            onToggle={toggleDomain}
            onSelect={selectObjectType}
          />
        ))}
      </aside>

      {/* ── 우측: Model Canvas ── */}
      <main className="flex-1 min-w-0 overflow-hidden">
        {selectedOt ? (
          <ObjectTypeDetail
            objectType={selectedOt}
            allObjectTypes={objectTypes}
          />
        ) : (
          /* 빈 상태 — .pen 디자인 사양 */
          <div className="flex flex-col items-center justify-center h-full gap-4 p-6">
            <Boxes className="h-12 w-12 text-border" />
            <p className="text-[13px] text-muted-foreground">
              {t('domainExt.selectDomainHint', 'Select a domain to view its model')}
            </p>
          </div>
        )}
      </main>

      {/* ── 다이얼로그 ── */}
      <CreateObjectTypeDialog
        open={isCreateDialogOpen}
        onClose={closeCreateDialog}
        onCreated={() => refetch()}
      />

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

// ── 트리 레벨별 들여쓰기 Tailwind 클래스 ──
// Tailwind JIT는 동적 클래스명을 감지하지 못하므로 정적 매핑 사용
const INDENT_DOMAIN: Record<number, string> = {
  0: 'pl-2',
  1: 'pl-6',
  2: 'pl-10',
  3: 'pl-14',
};

const INDENT_OBJECT: Record<number, string> = {
  0: 'pl-6',
  1: 'pl-10',
  2: 'pl-14',
  3: 'pl-[72px]',
};

// ── Tree Node 재귀 컴포넌트 ──

interface TreeNodeItemProps {
  node: TreeNode;
  level: number;
  expandedDomains: Set<string>;
  selectedId: string | null;
  onToggle: (id: string) => void;
  onSelect: (id: string | null) => void;
}

function TreeNodeItem({ node, level, expandedDomains, selectedId, onToggle, onSelect }: TreeNodeItemProps) {
  const isDomain = node.type === 'domain';
  const isExpanded = expandedDomains.has(node.id);
  const isSelected = node.id === selectedId;

  if (isDomain) {
    const indent = INDENT_DOMAIN[level] ?? 'pl-2';

    return (
      <div>
        <button
          type="button"
          onClick={() => onToggle(node.id)}
          className={[
            'flex items-center gap-1.5 w-full rounded pr-2 py-1 text-left transition-colors',
            'hover:bg-muted/50',
            indent,
          ].join(' ')}
        >
          {isExpanded ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
          )}
          <Folder
            className={`h-3.5 w-3.5 shrink-0 ${isExpanded ? 'text-primary' : 'text-muted-foreground'}`}
          />
          <span
            className={`text-xs truncate ${isExpanded ? 'font-medium text-foreground' : 'text-muted-foreground'}`}
          >
            {node.label}
          </span>
        </button>

        {/* 자식 노드 */}
        {isExpanded && node.children?.map((child) => (
          <TreeNodeItem
            key={child.id}
            node={child}
            level={level + 1}
            expandedDomains={expandedDomains}
            selectedId={selectedId}
            onToggle={onToggle}
            onSelect={onSelect}
          />
        ))}
      </div>
    );
  }

  // object 타입 노드
  const indent = INDENT_OBJECT[level] ?? 'pl-6';

  return (
    <button
      type="button"
      onClick={() => onSelect(node.id)}
      className={[
        'flex items-center gap-1.5 w-full rounded pr-2 py-1 text-left transition-colors',
        isSelected ? 'bg-muted' : 'hover:bg-muted/50',
        indent,
      ].join(' ')}
    >
      <Box className="h-3.5 w-3.5 text-blue-500 shrink-0" />
      <span className={`text-xs truncate ${isSelected ? 'font-medium text-foreground' : 'text-foreground'}`}>
        {node.label}
      </span>
    </button>
  );
}
