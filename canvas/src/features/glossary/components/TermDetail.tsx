/**
 * TermDetail — 용어 상세 패널 (우측)
 * 선택된 용어의 정의, 동의어, 관련 테이블, 온톨로지 매핑 표시
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Trash2, BookOpen, Table2, Network, Tag } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useGlossaryStore } from '../store/useGlossaryStore';
import { useDeleteTerm } from '../hooks/useGlossary';
import type { GlossaryTerm, TermStatus } from '../types/glossary';

/** 상태별 배지 스타일 */
const statusConfig: Record<TermStatus, { className: string; labelKey: string }> = {
  draft: {
    className: 'bg-muted text-muted-foreground',
    labelKey: 'glossary.status.draft',
  },
  approved: {
    className: 'bg-emerald-500/15 text-emerald-600',
    labelKey: 'glossary.status.approved',
  },
  deprecated: {
    className: 'bg-destructive/15 text-destructive',
    labelKey: 'glossary.status.deprecated',
  },
};

export const TermDetail: React.FC = () => {
  const { t } = useTranslation();
  const { selectedTerm, selectedGlossary, openTermEditor, setSelectedTerm } =
    useGlossaryStore();

  const glossaryId = selectedGlossary?.id ?? '';
  const deleteMut = useDeleteTerm(glossaryId);

  if (!selectedTerm) {
    // 빈 상태 — 용어 미선택
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-3 p-8">
        <BookOpen className="h-12 w-12 opacity-40" />
        <p className="text-sm">{t('glossary.detail.noSelection')}</p>
      </div>
    );
  }

  const term = selectedTerm;
  const sc = statusConfig[term.status];

  /** 삭제 처리 */
  const handleDelete = () => {
    if (!window.confirm(t('glossary.term.confirmDelete', { name: term.name }))) return;
    deleteMut.mutate(term.id, {
      onSuccess: () => setSelectedTerm(null),
    });
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {/* 상단 — 이름 + 액션 */}
      <header className="flex items-start justify-between px-6 py-5 border-b">
        <div className="space-y-1.5 min-w-0">
          <h2 className="text-xl font-semibold truncate">{term.name}</h2>
          <div className="flex items-center gap-2">
            <Badge className={sc.className}>{t(sc.labelKey)}</Badge>
            {term.category && (
              <Badge variant="outline" className="text-xs">
                <Tag className="h-3 w-3 mr-1" />
                {term.category}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex gap-1.5 shrink-0">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => openTermEditor(term)}
            aria-label={t('glossary.term.edit')}
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-destructive hover:text-destructive"
            onClick={handleDelete}
            disabled={deleteMut.isPending}
            aria-label={t('common.delete')}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* 본문 섹션들 */}
      <div className="px-6 py-5 space-y-6">
        {/* 정의 */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            {t('glossary.term.definition')}
          </h3>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {term.definition || (
              <span className="text-muted-foreground italic">{t('glossary.detail.noDefinition')}</span>
            )}
          </p>
        </section>

        {/* 소유자 */}
        {term.owner && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              {t('glossary.term.owner')}
            </h3>
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-semibold">
                {term.owner.charAt(0).toUpperCase()}
              </div>
              <span className="text-sm">{term.owner}</span>
            </div>
          </section>
        )}

        {/* 동의어 */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            {t('glossary.term.synonyms')}
          </h3>
          {term.synonyms.length === 0 ? (
            <span className="text-xs text-muted-foreground">{t('glossary.term.noSynonyms')}</span>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {term.synonyms.map((s, i) => (
                <Badge key={i} variant="secondary">{s}</Badge>
              ))}
            </div>
          )}
        </section>

        {/* 태그 */}
        {term.tags.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              {t('glossary.term.tags')}
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {term.tags.map((tg, i) => (
                <Badge key={i} variant="outline" className="bg-emerald-500/10 text-emerald-600">
                  {tg}
                </Badge>
              ))}
            </div>
          </section>
        )}

        {/* 관련 테이블 */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            <Table2 className="h-3.5 w-3.5 inline mr-1" />
            {t('glossary.term.relatedTables')}
          </h3>
          {term.relatedTables.length === 0 ? (
            <span className="text-xs text-muted-foreground">{t('glossary.term.noRelatedTables')}</span>
          ) : (
            <div className="space-y-1">
              {term.relatedTables.map((rt, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 px-3 py-2 rounded-md bg-muted text-sm"
                >
                  <Table2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <span className="font-medium">{rt.tableName}</span>
                  {rt.columnName && (
                    <span className="text-muted-foreground">.{rt.columnName}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 온톨로지 매핑 */}
        {term.ontologyNodeId && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              <Network className="h-3.5 w-3.5 inline mr-1" />
              {t('glossary.term.ontologyMapping')}
            </h3>
            <Badge variant="outline" className="font-mono text-xs">
              {term.ontologyNodeId}
            </Badge>
          </section>
        )}

        {/* 메타 — 생성/수정일 */}
        <section className="pt-2 border-t">
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div>
              <span className="font-medium">{t('glossary.detail.createdAt')}: </span>
              {new Date(term.created_at).toLocaleDateString()}
            </div>
            <div>
              <span className="font-medium">{t('glossary.detail.updatedAt')}: </span>
              {new Date(term.updated_at).toLocaleDateString()}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
