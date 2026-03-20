/**
 * FieldEditor — ObjectType 필드(컬럼) 편집기
 *
 * 소스 컬럼 매핑, 표시명, 타입, PK/FK 플래그, 표시 여부를 관리한다.
 * KAIR CreateObjectTypeDialog.vue의 컬럼 편집 영역을 React + Tailwind로 재구현.
 */

import React, { useCallback } from 'react';
import {
  Eye,
  EyeOff,
  Trash2,
  GripVertical,
  Plus,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { ObjectTypeField } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface FieldEditorProps {
  /** 현재 필드 목록 */
  fields: ObjectTypeField[];
  /** 필드 목록 변경 콜백 */
  onChange: (fields: ObjectTypeField[]) => void;
  /** 읽기 전용 모드 */
  readOnly?: boolean;
}

// ──────────────────────────────────────
// 데이터 타입 옵션
// ──────────────────────────────────────

const DATA_TYPES = [
  'string',
  'integer',
  'float',
  'boolean',
  'date',
  'datetime',
  'json',
  'text',
  'uuid',
] as const;

// ──────────────────────────────────────
// 유틸
// ──────────────────────────────────────

let _fieldSeq = 0;
function nextFieldId(): string {
  return `field_${Date.now()}_${++_fieldSeq}`;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const FieldEditor: React.FC<FieldEditorProps> = ({
  fields,
  onChange,
  readOnly = false,
}) => {
  // 필드 값 변경
  const updateField = useCallback(
    (index: number, patch: Partial<ObjectTypeField>) => {
      const next = fields.map((f, i) => (i === index ? { ...f, ...patch } : f));
      onChange(next);
    },
    [fields, onChange],
  );

  // 필드 삭제
  const removeField = useCallback(
    (index: number) => {
      onChange(fields.filter((_, i) => i !== index));
    },
    [fields, onChange],
  );

  // 새 필드 추가
  const addField = useCallback(() => {
    const newField: ObjectTypeField = {
      id: nextFieldId(),
      name: '',
      displayName: '',
      sourceColumn: '',
      dataType: 'string',
      isPrimaryKey: false,
      isForeignKey: false,
      isVisible: true,
    };
    onChange([...fields, newField]);
  }, [fields, onChange]);

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          필드 정의 ({fields.length})
        </h3>
        {!readOnly && (
          <Button variant="outline" size="sm" onClick={addField}>
            <Plus className="h-3.5 w-3.5 mr-1" />
            필드 추가
          </Button>
        )}
      </div>

      {/* 테이블 */}
      {fields.length === 0 ? (
        <div className="text-sm text-muted-foreground text-center py-6 border border-dashed border-border rounded-lg">
          필드가 없습니다. &quot;필드 추가&quot; 버튼을 클릭하거나 테이블에서 자동 생성하세요.
        </div>
      ) : (
        <div className="border border-border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/30">
                {!readOnly && <TableHead className="w-8" />}
                <TableHead className="text-xs">필드명</TableHead>
                <TableHead className="text-xs">표시명</TableHead>
                <TableHead className="text-xs">소스 컬럼</TableHead>
                <TableHead className="text-xs w-28">타입</TableHead>
                <TableHead className="text-xs w-10 text-center">PK</TableHead>
                <TableHead className="text-xs w-10 text-center">FK</TableHead>
                <TableHead className="text-xs w-10 text-center">표시</TableHead>
                {!readOnly && <TableHead className="text-xs w-10" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {fields.map((field, idx) => (
                <TableRow key={field.id} className="group">
                  {/* 드래그 핸들 */}
                  {!readOnly && (
                    <TableCell className="w-8 px-1">
                      <GripVertical className="h-3.5 w-3.5 text-muted-foreground/50 cursor-grab" />
                    </TableCell>
                  )}

                  {/* 필드명 */}
                  <TableCell className="py-1">
                    <Input
                      value={field.name}
                      onChange={(e) => updateField(idx, { name: e.target.value })}
                      className="h-7 text-xs"
                      placeholder="field_name"
                      readOnly={readOnly}
                    />
                  </TableCell>

                  {/* 표시명 */}
                  <TableCell className="py-1">
                    <Input
                      value={field.displayName}
                      onChange={(e) => updateField(idx, { displayName: e.target.value })}
                      className="h-7 text-xs"
                      placeholder="표시 이름"
                      readOnly={readOnly}
                    />
                  </TableCell>

                  {/* 소스 컬럼 */}
                  <TableCell className="py-1">
                    <Input
                      value={field.sourceColumn}
                      onChange={(e) => updateField(idx, { sourceColumn: e.target.value })}
                      className="h-7 text-xs"
                      placeholder="column_name"
                      readOnly={readOnly}
                    />
                  </TableCell>

                  {/* 데이터 타입 */}
                  <TableCell className="py-1 w-28">
                    <Select
                      value={field.dataType}
                      onValueChange={(v) => updateField(idx, { dataType: v })}
                      disabled={readOnly}
                    >
                      <SelectTrigger className="h-7 text-xs w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DATA_TYPES.map((t) => (
                          <SelectItem key={t} value={t} className="text-xs">
                            {t}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>

                  {/* PK */}
                  <TableCell className="text-center py-1 w-10">
                    <div className="flex justify-center" title="Primary Key">
                      <Checkbox
                        checked={field.isPrimaryKey}
                        onCheckedChange={(c) => updateField(idx, { isPrimaryKey: !!c })}
                        disabled={readOnly}
                      />
                    </div>
                  </TableCell>

                  {/* FK */}
                  <TableCell className="text-center py-1 w-10">
                    <div className="flex justify-center" title="Foreign Key">
                      <Checkbox
                        checked={field.isForeignKey}
                        onCheckedChange={(c) => updateField(idx, { isForeignKey: !!c })}
                        disabled={readOnly}
                      />
                    </div>
                  </TableCell>

                  {/* 표시 여부 */}
                  <TableCell className="text-center py-1 w-10">
                    <button
                      type="button"
                      className="p-1 rounded hover:bg-muted"
                      onClick={() => !readOnly && updateField(idx, { isVisible: !field.isVisible })}
                      disabled={readOnly}
                    >
                      {field.isVisible ? (
                        <Eye className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </button>
                  </TableCell>

                  {/* 삭제 */}
                  {!readOnly && (
                    <TableCell className="py-1 w-10">
                      <button
                        type="button"
                        className="p-1 rounded opacity-0 group-hover:opacity-100 text-destructive hover:bg-destructive/10"
                        onClick={() => removeField(idx)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
};
