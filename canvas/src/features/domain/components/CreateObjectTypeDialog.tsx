/**
 * CreateObjectTypeDialog — ObjectType 생성 다이얼로그
 *
 * 2가지 생성 방식:
 *   1) DB 테이블 기반 자동 생성 (Introspection)
 *   2) 수동 필드 정의
 *
 * KAIR CreateObjectTypeDialog.vue를 React + Tailwind로 재구현.
 */

import React, { useState, useCallback } from 'react';
import {
  Database,
  Pencil,
  Wand2,
  Loader2,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { FieldEditor } from './FieldEditor';
import { useCreateObjectType, useGenerateFromTable } from '../hooks/useObjectTypes';
import type { ObjectTypeField, CreateObjectTypePayload, ObjectTypeStatus } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface CreateObjectTypeDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
}

// ──────────────────────────────────────
// 유틸
// ──────────────────────────────────────

type CreationMode = 'auto' | 'manual';

let _seq = 0;
function tempId() {
  return `tmp_${Date.now()}_${++_seq}`;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const CreateObjectTypeDialog: React.FC<CreateObjectTypeDialogProps> = ({
  open,
  onClose,
  onCreated,
}) => {
  // ── 모드 ──
  const [mode, setMode] = useState<CreationMode>('auto');

  // ── 기본 정보 ──
  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');

  // ── 자동 생성 (Introspection) ──
  const [datasource, setDatasource] = useState('');
  const [schema, setSchema] = useState('');
  const [table, setTable] = useState('');

  // ── 수동 필드 ──
  const [fields, setFields] = useState<ObjectTypeField[]>([]);

  // ── 뮤테이션 ──
  const createMutation = useCreateObjectType();
  const generateMutation = useGenerateFromTable();

  const isLoading = createMutation.isPending || generateMutation.isPending;

  // 리셋
  const reset = useCallback(() => {
    setMode('auto');
    setName('');
    setDisplayName('');
    setDescription('');
    setDatasource('');
    setSchema('');
    setTable('');
    setFields([]);
    createMutation.reset();
    generateMutation.reset();
  }, [createMutation, generateMutation]);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  // 자동 생성 제출
  const handleAutoGenerate = useCallback(async () => {
    if (!datasource || !schema || !table) return;
    try {
      await generateMutation.mutateAsync({ datasource, schema, table });
      onCreated?.();
      handleClose();
    } catch {
      // 에러는 generateMutation.error에서 처리
    }
  }, [datasource, schema, table, generateMutation, onCreated, handleClose]);

  // 수동 생성 제출
  const handleManualCreate = useCallback(async () => {
    if (!name.trim()) return;
    const payload: CreateObjectTypePayload = {
      name: name.trim(),
      displayName: displayName.trim() || name.trim(),
      description: description.trim() || undefined,
      fields: fields.map((f) => ({
        name: f.name,
        displayName: f.displayName,
        sourceColumn: f.sourceColumn,
        dataType: f.dataType,
        isPrimaryKey: f.isPrimaryKey,
        isForeignKey: f.isForeignKey,
        isVisible: f.isVisible,
        description: f.description,
      })),
    };
    try {
      await createMutation.mutateAsync(payload);
      onCreated?.();
      handleClose();
    } catch {
      // 에러는 createMutation.error에서 처리
    }
  }, [name, displayName, description, fields, createMutation, onCreated, handleClose]);

  const errorMessage =
    (createMutation.error as Error)?.message ||
    (generateMutation.error as Error)?.message ||
    null;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-card border border-border rounded-lg w-[640px] max-h-[85vh] overflow-auto shadow-xl">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h2 className="text-sm font-semibold text-foreground">새 ObjectType 생성</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              DB 테이블에서 자동 생성하거나 필드를 직접 정의하세요.
            </p>
          </div>
          <button type="button" onClick={handleClose} className="text-muted-foreground hover:text-foreground p-1">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 탭 전환 */}
        <div className="flex border-b border-border">
          <button
            type="button"
            onClick={() => setMode('auto')}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors border-b-2',
              mode === 'auto'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            <Wand2 className="h-3.5 w-3.5" />
            테이블 자동 생성
          </button>
          <button
            type="button"
            onClick={() => setMode('manual')}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors border-b-2',
              mode === 'manual'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            <Pencil className="h-3.5 w-3.5" />
            수동 정의
          </button>
        </div>

        {/* 본문 */}
        <div className="p-5 space-y-4">
          {/* ── 자동 생성 ── */}
          {mode === 'auto' && (
            <>
              <p className="text-sm text-muted-foreground">
                데이터소스의 테이블을 선택하면 컬럼 정보를 자동으로 추출하여 ObjectType을 생성합니다.
              </p>
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">데이터소스 *</label>
                  <Input
                    value={datasource}
                    onChange={(e) => setDatasource(e.target.value)}
                    placeholder="my_datasource"
                    className="h-8 text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">스키마 *</label>
                  <Input
                    value={schema}
                    onChange={(e) => setSchema(e.target.value)}
                    placeholder="public"
                    className="h-8 text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">테이블 *</label>
                  <Input
                    value={table}
                    onChange={(e) => setTable(e.target.value)}
                    placeholder="orders"
                    className="h-8 text-sm"
                  />
                </div>
              </div>
            </>
          )}

          {/* ── 수동 정의 ── */}
          {mode === 'manual' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">이름 * (영문, snake_case)</label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value.replace(/\s+/g, '_'))}
                    placeholder="order_item"
                    className="h-8 text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground">표시명</label>
                  <Input
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="주문 항목"
                    className="h-8 text-sm"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">설명</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="이 ObjectType의 설명..."
                  className="w-full h-16 px-3 py-2 text-sm bg-background border border-border rounded-md resize-none text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* 필드 편집기 */}
              <FieldEditor fields={fields} onChange={setFields} />
            </>
          )}

          {/* 에러 표시 */}
          {errorMessage && (
            <div className="px-3 py-2 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm">
              {errorMessage}
            </div>
          )}
        </div>

        {/* 푸터 */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border">
          <Button variant="ghost" size="sm" onClick={handleClose} disabled={isLoading}>
            취소
          </Button>
          {mode === 'auto' ? (
            <Button
              size="sm"
              onClick={handleAutoGenerate}
              disabled={!datasource || !schema || !table || isLoading}
            >
              {isLoading && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              <Database className="h-3.5 w-3.5 mr-1" />
              자동 생성
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={handleManualCreate}
              disabled={!name.trim() || isLoading}
            >
              {isLoading && <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />}
              생성
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
