/**
 * WorkflowToolbar — 워크플로 노드 추가 도구 모음
 *
 * 5종 노드 타입에 대해 클릭하면 캔버스에 해당 노드를 추가한다.
 * 저장/불러오기/리셋 버튼도 포함.
 */

import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Zap,
  Filter,
  Play,
  Shield,
  GitBranch,
  Save,
  FileInput,
  RotateCcw,
  Plus,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useWorkflowEditorStore } from '../store/useWorkflowEditorStore';
import type {
  WorkflowNodeType,
  NodeTypeInfo,
} from '../types/workflowEditor.types';
import { DEFAULT_NODE_DATA } from '../types/workflowEditor.types';

// ──────────────────────────────────────
// 노드 타입 메타 정보
// ──────────────────────────────────────

// 노드 타입 메타 (label/description은 i18n 키로 참조)
const NODE_TYPE_KEYS: (NodeTypeInfo & { labelKey: string; descKey: string })[] = [
  {
    type: 'trigger',
    label: '', // 런타임에 t()로 채움
    labelKey: 'workflowEditor.toolbar.trigger',
    color: 'text-amber-400',
    borderColor: 'border-amber-500/30',
    description: '',
    descKey: 'workflowEditor.trigger.title',
  },
  {
    type: 'condition',
    label: '',
    labelKey: 'workflowEditor.toolbar.condition',
    color: 'text-sky-400',
    borderColor: 'border-sky-500/30',
    description: '',
    descKey: 'workflowEditor.condition.title',
  },
  {
    type: 'action',
    label: '',
    labelKey: 'workflowEditor.toolbar.action',
    color: 'text-emerald-400',
    borderColor: 'border-emerald-500/30',
    description: '',
    descKey: 'workflowEditor.action.title',
  },
  {
    type: 'policy',
    label: '',
    labelKey: 'workflowEditor.toolbar.policy',
    color: 'text-violet-400',
    borderColor: 'border-violet-500/30',
    description: '',
    descKey: 'workflowEditor.policy.title',
  },
  {
    type: 'gateway',
    label: '',
    labelKey: 'workflowEditor.toolbar.gateway',
    color: 'text-rose-400',
    borderColor: 'border-rose-500/30',
    description: '',
    descKey: 'workflowEditor.gateway.title',
  },
];

// 노드 타입별 아이콘 매핑
const NODE_ICONS: Record<WorkflowNodeType, React.FC<{ className?: string }>> = {
  trigger: Zap,
  condition: Filter,
  action: Play,
  policy: Shield,
  gateway: GitBranch,
};

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const WorkflowToolbar: React.FC = () => {
  const { t } = useTranslation();
  const addNode = useWorkflowEditorStore((s) => s.addNode);
  const nodes = useWorkflowEditorStore((s) => s.nodes);
  const save = useWorkflowEditorStore((s) => s.save);
  const reset = useWorkflowEditorStore((s) => s.reset);
  const isDirty = useWorkflowEditorStore((s) => s.isDirty);

  // 번역된 노드 타입 정보
  const NODE_TYPES = NODE_TYPE_KEYS.map((n) => ({
    ...n,
    label: t(n.labelKey),
    description: t(n.descKey),
  }));

  /** 새 노드를 캔버스에 추가 (기존 노드 수에 따라 위치 오프셋) */
  const handleAddNode = useCallback(
    (type: WorkflowNodeType) => {
      const offset = nodes.length;
      // 좌→우로 배치: 각 노드를 160px 간격으로 배치
      const x = 100 + (offset % 6) * 160;
      const y = 100 + Math.floor(offset / 6) * 120;

      addNode({
        id: crypto.randomUUID(),
        type,
        label: `${t(`workflowEditor.toolbar.${type}`)} ${offset + 1}`,
        position: { x, y },
        data: DEFAULT_NODE_DATA[type](),
      });
    },
    [addNode, nodes.length, t],
  );

  return (
    <div className="flex items-center gap-1 px-3 py-2 border-b border-border bg-card">
      {/* 노드 추가 버튼들 */}
      <TooltipProvider delayDuration={200}>
        {NODE_TYPES.map((info) => {
          const Icon = NODE_ICONS[info.type];
          return (
            <Tooltip key={info.type}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`h-8 gap-1.5 text-xs ${info.color} hover:bg-muted`}
                  onClick={() => handleAddNode(info.type)}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">{info.label}</span>
                  <Plus className="h-3 w-3 opacity-50" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                {info.description}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </TooltipProvider>

      <Separator orientation="vertical" className="h-5 mx-2" />

      {/* 저장 / 리셋 */}
      <Button
        variant="ghost"
        size="sm"
        className="h-8 gap-1.5 text-xs"
        onClick={save}
        disabled={!isDirty}
        title={t('common.save')}
      >
        <Save className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">{t('common.save')}</span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        className="h-8 gap-1.5 text-xs text-muted-foreground"
        onClick={reset}
        title={t('common.reset')}
      >
        <RotateCcw className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">{t('common.reset')}</span>
      </Button>

      {/* 변경 여부 인디케이터 */}
      {isDirty && (
        <span className="ml-auto text-[10px] text-amber-500">
          {t('workflowEditor.toolbar.unsavedChanges')}
        </span>
      )}
    </div>
  );
};
