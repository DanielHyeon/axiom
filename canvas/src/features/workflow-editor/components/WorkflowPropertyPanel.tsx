/**
 * WorkflowPropertyPanel — 선택 노드 속성 편집 패널 (우측 30%)
 *
 * 노드 타입에 따라 적절한 편집 폼을 렌더링하는 오케스트레이터.
 * 실제 폼 UI는 property-forms/ 디렉토리의 개별 컴포넌트에 위임한다:
 * - TriggerForm: 이벤트 유형 셀렉터
 * - ConditionForm: GWT Given 조건 편집기
 * - ActionForm: GWT Then 액션 편집기
 * - PolicyForm: 정책 설정
 * - GatewayForm: 분기 모드 선택
 */

import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useWorkflowEditorStore } from '../store/useWorkflowEditorStore';
import type {
  TriggerData,
  ConditionData,
  ActionData,
  PolicyData,
  GatewayData,
} from '../types/workflowEditor.types';
import {
  TriggerForm,
  ConditionForm,
  ActionForm,
  PolicyForm,
  GatewayForm,
} from './property-forms';

// ── 속성 패널 메인 컴포넌트 ──

export const WorkflowPropertyPanel: React.FC = () => {
  const { t } = useTranslation();
  const selectedNodeId = useWorkflowEditorStore((s) => s.selectedNodeId);
  const nodes = useWorkflowEditorStore((s) => s.nodes);
  const updateNode = useWorkflowEditorStore((s) => s.updateNode);
  const updateNodeData = useWorkflowEditorStore((s) => s.updateNodeData);
  const removeNode = useWorkflowEditorStore((s) => s.removeNode);
  const setSelectedNode = useWorkflowEditorStore((s) => s.setSelectedNode);

  // 현재 선택된 노드 찾기
  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );

  // 노드 라벨 변경 핸들러
  const handleLabelChange = useCallback(
    (label: string) => {
      if (selectedNodeId) updateNode(selectedNodeId, { label });
    },
    [selectedNodeId, updateNode],
  );

  // 노드 삭제 핸들러
  const handleDelete = useCallback(() => {
    if (selectedNodeId) {
      removeNode(selectedNodeId);
    }
  }, [selectedNodeId, removeNode]);

  // 선택 없음 상태 — 안내 메시지 표시
  if (!selectedNode) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        <p>{t('workflowEditor.property.selectNode')}</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-4">
        {/* 헤더: 노드 이름 + 닫기 */}
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            {t('workflowEditor.property.title')}
          </h3>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setSelectedNode(null)}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* 공통: 라벨 편집 */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t('workflowEditor.property.label')}</Label>
          <Input
            value={selectedNode.label}
            onChange={(e) => handleLabelChange(e.target.value)}
            className="h-8 text-sm"
            placeholder={t('workflowEditor.property.label')}
          />
        </div>

        {/* 노드 타입 표시 */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t('workflowEditor.property.type')}</Label>
          <div className="text-xs font-mono text-muted-foreground bg-muted px-2 py-1 rounded">
            {selectedNode.type}
          </div>
        </div>

        <Separator />

        {/* 타입별 속성 폼 — 각 폼 컴포넌트에 위임 */}
        {selectedNode.type === 'trigger' && (
          <TriggerForm
            data={selectedNode.data as TriggerData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}
        {selectedNode.type === 'condition' && (
          <ConditionForm
            data={selectedNode.data as ConditionData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}
        {selectedNode.type === 'action' && (
          <ActionForm
            data={selectedNode.data as ActionData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}
        {selectedNode.type === 'policy' && (
          <PolicyForm
            data={selectedNode.data as PolicyData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}
        {selectedNode.type === 'gateway' && (
          <GatewayForm
            data={selectedNode.data as GatewayData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}

        <Separator />

        {/* 삭제 버튼 */}
        <Button
          variant="destructive"
          size="sm"
          className="w-full gap-1.5"
          onClick={handleDelete}
        >
          <Trash2 className="h-3.5 w-3.5" />
          {t('common.delete')}
        </Button>
      </div>
    </ScrollArea>
  );
};
