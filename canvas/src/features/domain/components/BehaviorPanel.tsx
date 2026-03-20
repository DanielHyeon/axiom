/**
 * BehaviorPanel — 행동 목록 패널
 *
 * ObjectType에 연결된 Behavior 목록을 보여주고, 추가/편집/실행 진입점을 제공한다.
 * KAIR BehaviorDialog.vue의 행동 타입 아이콘 + 목록 UI를 React로 재구현.
 */

import React from 'react';
import {
  Globe,
  Code2,
  FileCode,
  Table2,
  Zap,
  Play,
  Pencil,
  Plus,
  Power,
  PowerOff,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
// Switch는 기본 HTML checkbox로 대체
import { cn } from '@/lib/utils';
import type { Behavior, BehaviorType, BehaviorTrigger } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface BehaviorPanelProps {
  /** Behavior 목록 */
  behaviors: Behavior[];
  /** 추가 버튼 콜백 */
  onAdd: () => void;
  /** 편집 콜백 */
  onEdit: (behavior: Behavior) => void;
  /** 실행 콜백 */
  onExecute: (behavior: Behavior) => void;
  /** 활성/비활성 토글 콜백 */
  onToggle?: (behavior: Behavior, enabled: boolean) => void;
  /** 읽기 전용 */
  readOnly?: boolean;
}

// ──────────────────────────────────────
// 타입별 아이콘 매핑
// ──────────────────────────────────────

const TYPE_ICON: Record<BehaviorType, React.ReactNode> = {
  rest: <Globe className="h-4 w-4" />,
  javascript: <FileCode className="h-4 w-4" />,
  python: <Code2 className="h-4 w-4" />,
  dmn: <Table2 className="h-4 w-4" />,
};

const TYPE_LABEL: Record<BehaviorType, string> = {
  rest: 'REST API',
  javascript: 'JavaScript',
  python: 'Python',
  dmn: 'DMN 규칙',
};

const TYPE_COLOR: Record<BehaviorType, string> = {
  rest: 'text-sky-400 bg-sky-400/10',
  javascript: 'text-amber-400 bg-amber-400/10',
  python: 'text-emerald-400 bg-emerald-400/10',
  dmn: 'text-violet-400 bg-violet-400/10',
};

const TRIGGER_LABEL: Record<BehaviorTrigger, string> = {
  manual: '수동',
  on_create: '생성 시',
  on_update: '수정 시',
  scheduled: '스케줄',
};

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const BehaviorPanel: React.FC<BehaviorPanelProps> = ({
  behaviors,
  onAdd,
  onEdit,
  onExecute,
  onToggle,
  readOnly = false,
}) => {
  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Zap className="h-4 w-4 text-violet-400" />
          Behaviors ({behaviors.length})
        </h3>
        {!readOnly && (
          <Button variant="outline" size="sm" onClick={onAdd}>
            <Plus className="h-3.5 w-3.5 mr-1" />
            추가
          </Button>
        )}
      </div>

      {/* 목록 */}
      {behaviors.length === 0 ? (
        <div className="text-sm text-muted-foreground text-center py-6 border border-dashed border-border rounded-lg">
          정의된 Behavior가 없습니다.
        </div>
      ) : (
        <div className="space-y-2">
          {behaviors.map((b) => (
            <Card key={b.id} className="group">
              <CardContent className="p-3">
                <div className="flex items-center gap-3">
                  {/* 타입 아이콘 */}
                  <div className={cn('flex items-center justify-center w-8 h-8 rounded-md shrink-0', TYPE_COLOR[b.type])}>
                    {TYPE_ICON[b.type]}
                  </div>

                  {/* 이름 + 설명 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground truncate">
                        {b.name}
                      </span>
                      <Badge variant="outline" className="text-[10px] h-4 px-1">
                        {TYPE_LABEL[b.type]}
                      </Badge>
                      <Badge variant="outline" className="text-[10px] h-4 px-1">
                        {TRIGGER_LABEL[b.trigger]}
                      </Badge>
                    </div>
                    {b.description && (
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {b.description}
                      </p>
                    )}
                  </div>

                  {/* 활성/비활성 토글 */}
                  {onToggle && !readOnly && (
                    <button
                      type="button"
                      onClick={() => onToggle(b, !b.enabled)}
                      className={cn(
                        'relative shrink-0 w-8 h-5 rounded-full transition-colors',
                        b.enabled ? 'bg-primary' : 'bg-muted',
                      )}
                    >
                      <span
                        className={cn(
                          'absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform',
                          b.enabled && 'translate-x-3',
                        )}
                      />
                    </button>
                  )}

                  {/* 편집 버튼 */}
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 opacity-0 group-hover:opacity-100"
                      onClick={() => onEdit(b)}
                      title="편집"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                  )}

                  {/* 실행 버튼 */}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-emerald-400 opacity-0 group-hover:opacity-100"
                    onClick={() => onExecute(b)}
                    title="실행 테스트"
                    disabled={!b.enabled}
                  >
                    <Play className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
