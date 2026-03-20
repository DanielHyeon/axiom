/**
 * GlossaryEditorDialog — 용어집 생성/수정 다이얼로그
 * KAIR GlossaryModal.vue → React 이식
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, BookOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useGlossaryStore } from '../store/useGlossaryStore';
import { useCreateGlossary, useUpdateGlossary } from '../hooks/useGlossary';
import type { GlossaryType, GlossaryCreateRequest } from '../types/glossary';

// 용어집 유형 옵션
const TYPE_OPTIONS: { value: GlossaryType; labelKey: string; color: string }[] = [
  { value: 'Business', labelKey: 'glossary.type.business', color: '#3b82f6' },
  { value: 'Technical', labelKey: 'glossary.type.technical', color: '#8b5cf6' },
  { value: 'DataQuality', labelKey: 'glossary.type.dataQuality', color: '#10b981' },
];

export const GlossaryEditorDialog: React.FC = () => {
  const { t } = useTranslation();
  const {
    glossaryEditorOpen,
    editingGlossary,
    closeGlossaryEditor,
    setSelectedGlossary,
  } = useGlossaryStore();

  const isEdit = !!editingGlossary;
  const createMut = useCreateGlossary();
  const updateMut = useUpdateGlossary();

  // --- 폼 상태 ---
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState<GlossaryType>('Business');
  const [error, setError] = useState<string | null>(null);

  // 편집 대상 변경 시 폼 초기화
  useEffect(() => {
    if (editingGlossary) {
      setName(editingGlossary.name);
      setDescription(editingGlossary.description);
      setType(editingGlossary.type);
    } else {
      setName('');
      setDescription('');
      setType('Business');
    }
    setError(null);
  }, [editingGlossary, glossaryEditorOpen]);

  /** 저장 */
  const handleSave = useCallback(() => {
    if (!name.trim()) {
      setError(t('glossary.glossary.nameRequired'));
      return;
    }

    const payload: GlossaryCreateRequest = {
      name: name.trim(),
      description: description.trim(),
      type,
    };

    const promise = isEdit
      ? updateMut.mutateAsync({ id: editingGlossary!.id, data: payload })
      : createMut.mutateAsync(payload);

    promise
      .then((result) => {
        // 새로 생성된 경우 자동 선택
        if (!isEdit && result) {
          setSelectedGlossary(result);
        }
        closeGlossaryEditor();
      })
      .catch((e) => setError(e instanceof Error ? e.message : t('common.error')));
  }, [name, description, type, isEdit, editingGlossary, createMut, updateMut, closeGlossaryEditor, setSelectedGlossary, t]);

  if (!glossaryEditorOpen) return null;

  const isSaving = createMut.isPending || updateMut.isPending;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) closeGlossaryEditor(); }}
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? t('glossary.glossary.edit') : t('glossary.glossary.create')}
    >
      <div className="w-[480px] bg-background rounded-lg shadow-xl flex flex-col border">
        {/* 헤더 */}
        <header className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">
            {isEdit ? t('glossary.glossary.edit') : t('glossary.glossary.create')}
          </h2>
          <button
            onClick={closeGlossaryEditor}
            className="p-1.5 rounded-md text-muted-foreground hover:bg-muted transition-colors"
            aria-label={t('common.close')}
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        {/* 본문 */}
        <div className="px-6 py-5 space-y-5">
          {error && (
            <div className="px-4 py-3 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-sm">
              {error}
            </div>
          )}

          {/* 이름 */}
          <div className="space-y-1.5">
            <Label htmlFor="glossary-name">
              {t('glossary.glossary.name')} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="glossary-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('glossary.glossary.namePlaceholder')}
              autoFocus
            />
          </div>

          {/* 유형 */}
          <div className="space-y-1.5">
            <Label>{t('glossary.glossary.type')}</Label>
            <div className="flex flex-col gap-2">
              {TYPE_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-center gap-3 px-3 py-3 rounded-md border cursor-pointer transition-colors ${
                    type === opt.value
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="glossary-type"
                    value={opt.value}
                    checked={type === opt.value}
                    onChange={() => setType(opt.value)}
                    className="sr-only"
                  />
                  <span
                    className="w-4 h-4 rounded shrink-0"
                    style={{ backgroundColor: opt.color }}
                  />
                  <span className="text-sm">{t(opt.labelKey)}</span>
                </label>
              ))}
            </div>
          </div>

          {/* 설명 */}
          <div className="space-y-1.5">
            <Label htmlFor="glossary-desc">{t('glossary.glossary.description')}</Label>
            <Textarea
              id="glossary-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('glossary.glossary.descriptionPlaceholder')}
              rows={3}
            />
          </div>
        </div>

        {/* 푸터 */}
        <footer className="flex justify-end gap-3 px-6 py-4 border-t">
          <Button variant="outline" onClick={closeGlossaryEditor} disabled={isSaving}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving
              ? t('common.processing')
              : isEdit
                ? t('common.save')
                : t('glossary.glossary.createBtn')}
          </Button>
        </footer>
      </div>
    </div>
  );
};
