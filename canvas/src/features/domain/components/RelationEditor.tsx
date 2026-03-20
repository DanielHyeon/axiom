/**
 * RelationEditor — ObjectType 관계 정의 편집기
 *
 * 대상 ObjectType, 관계 유형, FK 컬럼을 관리한다.
 */

import React, { useCallback } from 'react';
import { Plus, Trash2, Link2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { ObjectTypeRelation, ObjectType, RelationType } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface RelationEditorProps {
  /** 현재 관계 목록 */
  relations: ObjectTypeRelation[];
  /** 변경 콜백 */
  onChange: (relations: ObjectTypeRelation[]) => void;
  /** 참조 가능한 ObjectType 목록 (현재 ObjectType 제외) */
  availableTargets: ObjectType[];
  /** 읽기 전용 */
  readOnly?: boolean;
}

// ──────────────────────────────────────
// 관계 유형 레이블
// ──────────────────────────────────────

const RELATION_LABELS: Record<RelationType, string> = {
  'one-to-many': '1:N',
  'many-to-one': 'N:1',
  'one-to-one': '1:1',
  'many-to-many': 'N:M',
};

// ──────────────────────────────────────
// 유틸
// ──────────────────────────────────────

let _relSeq = 0;
function nextRelId(): string {
  return `rel_${Date.now()}_${++_relSeq}`;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const RelationEditor: React.FC<RelationEditorProps> = ({
  relations,
  onChange,
  availableTargets,
  readOnly = false,
}) => {
  const update = useCallback(
    (idx: number, patch: Partial<ObjectTypeRelation>) => {
      onChange(relations.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
    },
    [relations, onChange],
  );

  const remove = useCallback(
    (idx: number) => {
      onChange(relations.filter((_, i) => i !== idx));
    },
    [relations, onChange],
  );

  const add = useCallback(() => {
    const newRel: ObjectTypeRelation = {
      id: nextRelId(),
      name: '',
      targetObjectTypeId: '',
      targetObjectTypeName: '',
      type: 'one-to-many',
      foreignKey: '',
    };
    onChange([...relations, newRel]);
  }, [relations, onChange]);

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Link2 className="h-4 w-4 text-primary" />
          관계 ({relations.length})
        </h3>
        {!readOnly && (
          <Button variant="outline" size="sm" onClick={add}>
            <Plus className="h-3.5 w-3.5 mr-1" />
            관계 추가
          </Button>
        )}
      </div>

      {/* 관계 목록 */}
      {relations.length === 0 ? (
        <div className="text-sm text-muted-foreground text-center py-6 border border-dashed border-border rounded-lg">
          정의된 관계가 없습니다.
        </div>
      ) : (
        <div className="space-y-2">
          {relations.map((rel, idx) => (
            <Card key={rel.id} className="group">
              <CardContent className="p-3 space-y-2">
                <div className="flex items-center gap-2">
                  {/* 관계명 */}
                  <Input
                    value={rel.name}
                    onChange={(e) => update(idx, { name: e.target.value })}
                    placeholder="관계명 (예: has_orders)"
                    className="h-7 text-xs flex-1"
                    readOnly={readOnly}
                  />

                  {/* 카디날리티 */}
                  <Select
                    value={rel.type}
                    onValueChange={(v) => update(idx, { type: v as RelationType })}
                    disabled={readOnly}
                  >
                    <SelectTrigger className="h-7 text-xs w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.entries(RELATION_LABELS) as [RelationType, string][]).map(([k, label]) => (
                        <SelectItem key={k} value={k} className="text-xs">
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {/* 삭제 */}
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 opacity-0 group-hover:opacity-100 text-destructive"
                      onClick={() => remove(idx)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {/* 대상 ObjectType */}
                  <Select
                    value={rel.targetObjectTypeId}
                    onValueChange={(v) => {
                      const target = availableTargets.find((t) => t.id === v);
                      update(idx, {
                        targetObjectTypeId: v,
                        targetObjectTypeName: target?.name ?? '',
                      });
                    }}
                    disabled={readOnly}
                  >
                    <SelectTrigger className="h-7 text-xs flex-1">
                      <SelectValue placeholder="대상 ObjectType 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableTargets.map((t) => (
                        <SelectItem key={t.id} value={t.id} className="text-xs">
                          {t.displayName || t.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {/* FK 컬럼 */}
                  <Input
                    value={rel.foreignKey}
                    onChange={(e) => update(idx, { foreignKey: e.target.value })}
                    placeholder="FK 컬럼"
                    className="h-7 text-xs w-36"
                    readOnly={readOnly}
                  />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
