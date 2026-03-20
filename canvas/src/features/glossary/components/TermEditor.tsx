/**
 * TermEditor — 용어 생성/수정 다이얼로그
 * shadcn/ui Dialog 패턴 대신 오버레이 직접 구현 (KAIR TermModal 이식)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { useGlossaryStore } from '../store/useGlossaryStore';
import { useCreateTerm, useUpdateTerm, useCategories } from '../hooks/useGlossary';
import type { GlossaryTerm, TermCreateRequest, TermStatus, RelatedTable } from '../types/glossary';

// 상태 옵션
const STATUS_OPTIONS: { value: TermStatus; labelKey: string }[] = [
  { value: 'draft', labelKey: 'glossary.status.draft' },
  { value: 'approved', labelKey: 'glossary.status.approved' },
  { value: 'deprecated', labelKey: 'glossary.status.deprecated' },
];

export const TermEditor: React.FC = () => {
  const { t } = useTranslation();
  const {
    termEditorOpen,
    editingTerm,
    selectedGlossary,
    closeTermEditor,
  } = useGlossaryStore();

  // 용어집이 선택되지 않았거나 다이얼로그가 닫혀있으면 렌더링 안 함
  const glossaryId = selectedGlossary?.id ?? '';
  const isEdit = !!editingTerm;

  const createMut = useCreateTerm(glossaryId);
  const updateMut = useUpdateTerm(glossaryId);
  const { data: categoryData } = useCategories();

  // --- 폼 상태 ---
  const [name, setName] = useState('');
  const [definition, setDefinition] = useState('');
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState<TermStatus>('draft');
  const [owner, setOwner] = useState('');
  const [synonyms, setSynonyms] = useState<string[]>([]);
  const [newSynonym, setNewSynonym] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState('');
  const [relatedTables, setRelatedTables] = useState<RelatedTable[]>([]);
  const [newTableName, setNewTableName] = useState('');
  const [newColumnName, setNewColumnName] = useState('');
  const [ontologyNodeId, setOntologyNodeId] = useState('');
  const [error, setError] = useState<string | null>(null);

  // 편집 대상이 바뀔 때 폼 초기화
  useEffect(() => {
    if (editingTerm) {
      setName(editingTerm.name);
      setDefinition(editingTerm.definition);
      setCategory(editingTerm.category);
      setStatus(editingTerm.status);
      setOwner(editingTerm.owner);
      setSynonyms([...editingTerm.synonyms]);
      setTags([...editingTerm.tags]);
      setRelatedTables([...editingTerm.relatedTables]);
      setOntologyNodeId(editingTerm.ontologyNodeId ?? '');
    } else {
      // 신규 — 초기화
      setName('');
      setDefinition('');
      setCategory('');
      setStatus('draft');
      setOwner('');
      setSynonyms([]);
      setTags([]);
      setRelatedTables([]);
      setOntologyNodeId('');
    }
    setError(null);
    setNewSynonym('');
    setNewTag('');
    setNewTableName('');
    setNewColumnName('');
  }, [editingTerm, termEditorOpen]);

  // --- 동의어 추가/삭제 ---
  const addSynonym = useCallback(() => {
    const trimmed = newSynonym.trim();
    if (trimmed && !synonyms.includes(trimmed)) {
      setSynonyms((prev) => [...prev, trimmed]);
      setNewSynonym('');
    }
  }, [newSynonym, synonyms]);

  const removeSynonym = useCallback((idx: number) => {
    setSynonyms((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // --- 태그 추가/삭제 ---
  const addTag = useCallback(() => {
    const trimmed = newTag.trim();
    if (trimmed && !tags.includes(trimmed)) {
      setTags((prev) => [...prev, trimmed]);
      setNewTag('');
    }
  }, [newTag, tags]);

  const removeTag = useCallback((idx: number) => {
    setTags((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // --- 관련 테이블 추가/삭제 ---
  const addRelatedTable = useCallback(() => {
    const tName = newTableName.trim();
    if (!tName) return;
    setRelatedTables((prev) => [
      ...prev,
      { tableName: tName, columnName: newColumnName.trim() || undefined },
    ]);
    setNewTableName('');
    setNewColumnName('');
  }, [newTableName, newColumnName]);

  const removeRelatedTable = useCallback((idx: number) => {
    setRelatedTables((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // --- 저장 ---
  const handleSave = useCallback(() => {
    if (!name.trim()) {
      setError(t('glossary.term.nameRequired'));
      return;
    }

    const payload: TermCreateRequest = {
      name: name.trim(),
      definition: definition.trim(),
      category,
      status,
      synonyms,
      relatedTables,
      ontologyNodeId: ontologyNodeId.trim() || undefined,
      owner: owner.trim(),
      tags,
    };

    const mutation = isEdit
      ? updateMut.mutateAsync({ termId: editingTerm!.id, data: payload })
      : createMut.mutateAsync(payload);

    mutation
      .then(() => closeTermEditor())
      .catch((e) => setError(e instanceof Error ? e.message : t('common.error')));
  }, [
    name, definition, category, status, synonyms, relatedTables,
    ontologyNodeId, owner, tags, isEdit, editingTerm, createMut,
    updateMut, closeTermEditor, t,
  ]);

  if (!termEditorOpen) return null;

  const isSaving = createMut.isPending || updateMut.isPending;

  return (
    // 오버레이
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) closeTermEditor(); }}
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? t('glossary.term.edit') : t('glossary.term.create')}
    >
      <div className="w-[580px] max-h-[90vh] bg-background rounded-lg shadow-xl flex flex-col border">
        {/* 헤더 */}
        <header className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">
            {isEdit ? t('glossary.term.edit') : t('glossary.term.create')}
          </h2>
          <button
            onClick={closeTermEditor}
            className="p-1.5 rounded-md text-muted-foreground hover:bg-muted transition-colors"
            aria-label={t('common.close')}
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        {/* 본문 — 스크롤 가능 */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {error && (
            <div className="px-4 py-3 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-sm">
              {error}
            </div>
          )}

          {/* 기본 정보 */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold border-b pb-2">{t('glossary.term.basicInfo')}</h3>

            <div className="space-y-1.5">
              <Label htmlFor="term-name">
                {t('glossary.term.name')} <span className="text-destructive">*</span>
              </Label>
              <Input
                id="term-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('glossary.term.namePlaceholder')}
                autoFocus
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="term-definition">{t('glossary.term.definition')}</Label>
              <Textarea
                id="term-definition"
                value={definition}
                onChange={(e) => setDefinition(e.target.value)}
                placeholder={t('glossary.term.definitionPlaceholder')}
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="term-status">{t('glossary.term.status')}</Label>
                <select
                  id="term-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value as TermStatus)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {t(opt.labelKey)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="term-category">{t('glossary.term.category')}</Label>
                <select
                  id="term-category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="">{t('glossary.term.selectCategory')}</option>
                  {(categoryData?.categories ?? []).map((c) => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="term-owner">{t('glossary.term.owner')}</Label>
              <Input
                id="term-owner"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder={t('glossary.term.ownerPlaceholder')}
              />
            </div>
          </section>

          {/* 동의어 */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold border-b pb-2">{t('glossary.term.synonyms')}</h3>
            <div className="flex gap-2">
              <Input
                value={newSynonym}
                onChange={(e) => setNewSynonym(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSynonym(); } }}
                placeholder={t('glossary.term.synonymPlaceholder')}
                className="h-8 text-sm"
              />
              <Button size="sm" variant="outline" className="h-8 px-2" onClick={addSynonym}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {synonyms.length === 0 && (
                <span className="text-xs text-muted-foreground">{t('glossary.term.noSynonyms')}</span>
              )}
              {synonyms.map((s, idx) => (
                <Badge key={idx} variant="secondary" className="gap-1">
                  {s}
                  <button onClick={() => removeSynonym(idx)} className="hover:text-destructive">
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </section>

          {/* 태그 */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold border-b pb-2">{t('glossary.term.tags')}</h3>
            <div className="flex gap-2">
              <Input
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                placeholder={t('glossary.term.tagPlaceholder')}
                className="h-8 text-sm"
              />
              <Button size="sm" variant="outline" className="h-8 px-2" onClick={addTag}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {tags.length === 0 && (
                <span className="text-xs text-muted-foreground">{t('glossary.term.noTags')}</span>
              )}
              {tags.map((tg, idx) => (
                <Badge key={idx} variant="outline" className="gap-1 bg-emerald-500/10 text-emerald-600">
                  {tg}
                  <button onClick={() => removeTag(idx)} className="hover:text-destructive">
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </section>

          {/* 관련 테이블/컬럼 매핑 */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold border-b pb-2">{t('glossary.term.relatedTables')}</h3>
            <div className="flex gap-2">
              <Input
                value={newTableName}
                onChange={(e) => setNewTableName(e.target.value)}
                placeholder={t('glossary.term.tablePlaceholder')}
                className="h-8 text-sm flex-1"
              />
              <Input
                value={newColumnName}
                onChange={(e) => setNewColumnName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRelatedTable(); } }}
                placeholder={t('glossary.term.columnPlaceholder')}
                className="h-8 text-sm flex-1"
              />
              <Button size="sm" variant="outline" className="h-8 px-2" onClick={addRelatedTable}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {relatedTables.length === 0 ? (
              <span className="text-xs text-muted-foreground">{t('glossary.term.noRelatedTables')}</span>
            ) : (
              <div className="space-y-1">
                {relatedTables.map((rt, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between px-2.5 py-1.5 rounded-md bg-muted text-sm"
                  >
                    <span>
                      <span className="font-medium">{rt.tableName}</span>
                      {rt.columnName && (
                        <span className="text-muted-foreground">.{rt.columnName}</span>
                      )}
                    </span>
                    <button
                      onClick={() => removeRelatedTable(idx)}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 온톨로지 매핑 */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold border-b pb-2">{t('glossary.term.ontologyMapping')}</h3>
            <div className="space-y-1.5">
              <Label htmlFor="term-ontology">{t('glossary.term.ontologyNodeId')}</Label>
              <Input
                id="term-ontology"
                value={ontologyNodeId}
                onChange={(e) => setOntologyNodeId(e.target.value)}
                placeholder={t('glossary.term.ontologyPlaceholder')}
              />
            </div>
          </section>
        </div>

        {/* 푸터 */}
        <footer className="flex justify-end gap-3 px-6 py-4 border-t">
          <Button variant="outline" onClick={closeTermEditor} disabled={isSaving}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? t('common.processing') : isEdit ? t('common.save') : t('common.add')}
          </Button>
        </footer>
      </div>
    </div>
  );
};
