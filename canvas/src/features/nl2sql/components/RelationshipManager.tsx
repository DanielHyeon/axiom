/**
 * RelationshipManager — FK 관계 편집기.
 *
 * 사용자가 테이블 간 FK 관계를 수동으로 추가/삭제할 수 있는 패널.
 * KAIR RelationshipManager.vue를 React+Tailwind 패턴으로 이식.
 *
 * 현재는 로컬 상태만 관리 (백엔드 API가 구현되면 TanStack Query 연동 예정).
 */

import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import {
  ArrowRight,
  Trash2,
  Plus,
  Layers,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { TableMeta } from '../types/nl2sql';
import type { SchemaRelationship } from '../types/schema';

// ─── Props ────────────────────────────────────────────────

interface RelationshipManagerProps {
  /** 사용 가능한 테이블 목록 */
  tables: TableMeta[];
  /** 현재 관계 목록 */
  relationships: SchemaRelationship[];
  /** 관계 추가 핸들러 */
  onAdd: (rel: Omit<SchemaRelationship, 'id'>) => void;
  /** 관계 삭제 핸들러 */
  onRemove: (rel: SchemaRelationship) => void;
  /** 새로고침 */
  onRefresh?: () => void;
  /** 테이블의 컬럼명 목록 조회 함수 */
  getColumnNames?: (tableName: string) => string[];
}

// ─── 새 관계 입력 폼 상태 ─────────────────────────────────

interface NewRelForm {
  fromTable: string;
  fromColumn: string;
  toTable: string;
  toColumn: string;
  description: string;
}

const EMPTY_FORM: NewRelForm = {
  fromTable: '',
  fromColumn: '',
  toTable: '',
  toColumn: '',
  description: '',
};

// ─── 컴포넌트 ─────────────────────────────────────────────

export function RelationshipManager({
  tables,
  relationships,
  onAdd,
  onRemove,
  onRefresh,
  getColumnNames,
}: RelationshipManagerProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<NewRelForm>(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);

  // from 테이블의 컬럼 목록
  const fromColumns = form.fromTable ? (getColumnNames?.(form.fromTable) ?? []) : [];
  const toColumns = form.toTable ? (getColumnNames?.(form.toTable) ?? []) : [];

  // 관계 추가
  const handleAdd = useCallback(() => {
    if (!form.fromTable || !form.fromColumn || !form.toTable || !form.toColumn) return;

    onAdd({
      fromTable: form.fromTable,
      fromColumn: form.fromColumn,
      toTable: form.toTable,
      toColumn: form.toColumn,
      cardinality: 'many-to-one',
      description: form.description || undefined,
      isInferred: false,
    });

    setForm(EMPTY_FORM);
    setShowForm(false);
  }, [form, onAdd]);

  // 사용자 관계만 필터 (추론된 관계 제외)
  const userRelationships = relationships.filter((r) => !r.isInferred);
  const inferredRelationships = relationships.filter((r) => r.isInferred);

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-foreground/50" />
          <span className="text-[13px] font-semibold text-foreground font-heading">
            {t('relationship.title')}
          </span>
        </div>
        {onRefresh && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            className="h-7 px-2 text-[11px]"
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            {t('common.refresh')}
          </Button>
        )}
      </div>

      {/* 사용자 관계 목록 */}
      <div className="space-y-1">
        <span className="text-[10px] text-foreground/40 font-mono uppercase tracking-[0.5px]">
          {t('relationship.userAdded')} ({userRelationships.length})
        </span>
        {userRelationships.length === 0 && (
          <p className="text-[11px] text-foreground/30 font-mono py-2">
            {t('relationship.noUserRelations')}
          </p>
        )}
        {userRelationships.map((rel, idx) => (
          <RelationshipRow
            key={`user-${idx}`}
            relationship={rel}
            onRemove={() => onRemove(rel)}
          />
        ))}
      </div>

      {/* 추론된 관계 목록 (접기/펼치기) */}
      {inferredRelationships.length > 0 && (
        <details className="group">
          <summary className="text-[10px] text-foreground/40 font-mono uppercase tracking-[0.5px] cursor-pointer hover:text-foreground/60 transition-colors">
            {t('relationship.inferred')} ({inferredRelationships.length})
          </summary>
          <div className="mt-1 space-y-1">
            {inferredRelationships.map((rel, idx) => (
              <RelationshipRow
                key={`inferred-${idx}`}
                relationship={rel}
                isInferred
              />
            ))}
          </div>
        </details>
      )}

      {/* 새 관계 추가 폼 */}
      {!showForm ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowForm(true)}
          className="h-8 text-[11px] border-dashed"
        >
          <Plus className="h-3 w-3 mr-1" />
          {t('relationship.addRelation')}
        </Button>
      ) : (
        <div className="space-y-2 p-3 bg-muted/50 rounded border border-border">
          <span className="text-[10px] font-medium text-foreground/50 font-mono uppercase">
            {t('relationship.newRelation')}
          </span>

          {/* From */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-foreground/40 font-mono">{t('relationship.fromTable')}</label>
              <select
                value={form.fromTable}
                onChange={(e) => setForm((p) => ({ ...p, fromTable: e.target.value, fromColumn: '' }))}
                className="w-full h-7 px-2 text-[11px] border border-border rounded bg-card font-mono"
              >
                <option value="">{t('relationship.select')}</option>
                {tables.map((t) => (
                  <option key={t.name} value={t.name}>{t.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-foreground/40 font-mono">{t('relationship.fromColumn')}</label>
              <select
                value={form.fromColumn}
                onChange={(e) => setForm((p) => ({ ...p, fromColumn: e.target.value }))}
                className="w-full h-7 px-2 text-[11px] border border-border rounded bg-card font-mono"
                disabled={!form.fromTable}
              >
                <option value="">{t('relationship.select')}</option>
                {fromColumns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          {/* To */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-foreground/40 font-mono">{t('relationship.toTable')}</label>
              <select
                value={form.toTable}
                onChange={(e) => setForm((p) => ({ ...p, toTable: e.target.value, toColumn: '' }))}
                className="w-full h-7 px-2 text-[11px] border border-border rounded bg-card font-mono"
              >
                <option value="">{t('relationship.select')}</option>
                {tables.map((t) => (
                  <option key={t.name} value={t.name}>{t.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-foreground/40 font-mono">{t('relationship.toColumn')}</label>
              <select
                value={form.toColumn}
                onChange={(e) => setForm((p) => ({ ...p, toColumn: e.target.value }))}
                className="w-full h-7 px-2 text-[11px] border border-border rounded bg-card font-mono"
                disabled={!form.toTable}
              >
                <option value="">{t('relationship.select')}</option>
                {toColumns.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          {/* 설명 */}
          <div>
            <label className="text-[10px] text-foreground/40 font-mono">{t('relationship.descriptionOptional')}</label>
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              placeholder={t('relationship.descriptionPlaceholder')}
              className="w-full h-7 px-2 text-[11px] border border-border rounded bg-card font-mono outline-none focus:border-blue-300"
            />
          </div>

          {/* 버튼 */}
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleAdd}
              disabled={!form.fromTable || !form.fromColumn || !form.toTable || !form.toColumn}
              className="h-7 text-[11px]"
            >
              {t('common.add')}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setForm(EMPTY_FORM); setShowForm(false); }}
              className="h-7 text-[11px]"
            >
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── 관계 행 ──────────────────────────────────────────────

interface RelationshipRowProps {
  relationship: SchemaRelationship;
  isInferred?: boolean;
  onRemove?: () => void;
}

function RelationshipRow({ relationship, isInferred, onRemove }: RelationshipRowProps) {
  const { t } = useTranslation();
  return (
    <div
      className={cn(
        'flex items-center gap-2 px-2 py-1.5 rounded text-[11px] font-mono',
        isInferred ? 'bg-muted/50 text-foreground/40' : 'bg-blue-50/50 text-foreground/70'
      )}
    >
      {/* From */}
      <span className="truncate max-w-[120px]" title={`${relationship.fromTable}.${relationship.fromColumn}`}>
        {relationship.fromTable}.<strong>{relationship.fromColumn}</strong>
      </span>

      <ArrowRight className="h-3 w-3 text-foreground/25 shrink-0" />

      {/* To */}
      <span className="truncate max-w-[120px]" title={`${relationship.toTable}.${relationship.toColumn}`}>
        {relationship.toTable}.<strong>{relationship.toColumn}</strong>
      </span>

      {/* 설명 */}
      {relationship.description && (
        <span className="text-[9px] text-foreground/30 truncate max-w-[80px]" title={relationship.description}>
          ({relationship.description})
        </span>
      )}

      {/* 삭제 버튼 (사용자 관계만) */}
      {onRemove && !isInferred && (
        <button
          type="button"
          onClick={onRemove}
          className="ml-auto p-0.5 rounded hover:bg-red-100 text-foreground/30 hover:text-red-500 transition-colors shrink-0"
          aria-label={t('relationship.deleteRelation')}
        >
          <Trash2 className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}
