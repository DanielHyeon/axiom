/**
 * GlossaryBrowser — 글로서리 메인 2컬럼 레이아웃
 *
 * 구조:
 *   ┌─────────────────────────────────────────────────────┐
 *   │ Header: 용어집 선택 + 새 용어집 + Import/Export     │
 *   ├──────────────────────┬──────────────────────────────┤
 *   │  TermList (좌측)     │  TermDetail (우측)           │
 *   │  - 검색              │  - 정의, 동의어              │
 *   │  - 카테고리 필터     │  - 관련 테이블               │
 *   │  - 알파벳 인덱스     │  - 온톨로지 매핑             │
 *   │  - 용어 리스트       │                              │
 *   └──────────────────────┴──────────────────────────────┘
 *
 * KAIR GlossaryTab.vue → React + shadcn/ui + Tailwind 이식
 */

import React, { useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  BookOpen,
  Plus,
  Pencil,
  Trash2,
  Download,
  Upload,
  ChevronDown,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useGlossaryStore } from '../store/useGlossaryStore';
import { useGlossaries, useDeleteGlossary } from '../hooks/useGlossary';
import { TermList } from './TermList';
import { TermDetail } from './TermDetail';
import { TermEditor } from './TermEditor';
import { GlossaryEditorDialog } from './GlossaryEditorDialog';
import { GlossaryImportExport } from './GlossaryImportExport';
import type { Glossary, GlossaryType } from '../types/glossary';

// 용어집 유형별 색상
const typeColorMap: Record<GlossaryType, string> = {
  Business: '#3b82f6',
  Technical: '#8b5cf6',
  DataQuality: '#10b981',
};

export const GlossaryBrowser: React.FC = () => {
  const { t } = useTranslation();
  const {
    selectedGlossary,
    setSelectedGlossary,
    openGlossaryEditor,
    openImportExport,
  } = useGlossaryStore();

  const { data: glossaryData, isLoading } = useGlossaries();
  const deleteMut = useDeleteGlossary();
  const glossaries: Glossary[] = glossaryData?.glossaries ?? [];

  // 첫 번째 용어집 자동 선택 (초기 로드 시)
  useEffect(() => {
    if (!selectedGlossary && glossaries.length > 0) {
      setSelectedGlossary(glossaries[0]);
    }
  }, [glossaries, selectedGlossary, setSelectedGlossary]);

  /** 용어집 삭제 */
  const handleDeleteGlossary = useCallback(
    (glossary: Glossary) => {
      if (!window.confirm(t('glossary.glossary.confirmDelete', { name: glossary.name }))) return;
      deleteMut.mutate(glossary.id, {
        onSuccess: () => {
          if (selectedGlossary?.id === glossary.id) {
            setSelectedGlossary(null);
          }
        },
      });
    },
    [deleteMut, selectedGlossary, setSelectedGlossary, t],
  );

  return (
    <div className="flex h-full bg-background">
      {/* ========== 사이드바: 용어집 목록 ========== */}
      <aside className="w-[260px] shrink-0 border-r flex flex-col bg-muted/30">
        {/* 사이드바 헤더 */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h3 className="text-sm font-semibold">{t('glossary.glossaries')}</h3>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            onClick={() => openGlossaryEditor()}
            aria-label={t('glossary.glossary.create')}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {/* 용어집 리스트 */}
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <span className="text-sm text-muted-foreground">{t('common.loading')}</span>
            </div>
          )}

          {!isLoading && glossaries.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center gap-3">
              <BookOpen className="h-10 w-10 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">{t('glossary.glossary.empty')}</p>
              <Button size="sm" onClick={() => openGlossaryEditor()}>
                <Plus className="h-4 w-4 mr-1" />
                {t('glossary.glossary.createFirst')}
              </Button>
            </div>
          )}

          {glossaries.map((g) => {
            const isActive = selectedGlossary?.id === g.id;
            return (
              <button
                key={g.id}
                onClick={() => setSelectedGlossary(g)}
                className={`group w-full flex items-center gap-2.5 px-3 py-2.5 rounded-md text-left transition-colors ${
                  isActive
                    ? 'bg-primary/10'
                    : 'hover:bg-muted'
                }`}
              >
                {/* 유형 아이콘 */}
                <span
                  className="w-6 h-6 rounded flex items-center justify-center shrink-0"
                  style={{ backgroundColor: typeColorMap[g.type] ?? '#6b7280' }}
                >
                  <BookOpen className="h-3.5 w-3.5 text-white" />
                </span>

                {/* 이름 */}
                <span
                  className={`flex-1 text-sm truncate ${
                    isActive ? 'font-semibold text-foreground' : 'text-foreground/80'
                  }`}
                >
                  {g.name}
                </span>

                {/* 용어 수 */}
                <Badge variant="secondary" className="h-5 px-1.5 text-[10px] shrink-0">
                  {g.termCount}
                </Badge>

                {/* Hover 시 편집/삭제 */}
                <div className="hidden group-hover:flex gap-0.5 shrink-0">
                  <button
                    onClick={(e) => { e.stopPropagation(); openGlossaryEditor(g); }}
                    className="p-1 rounded hover:bg-muted-foreground/10"
                    aria-label={t('glossary.glossary.edit')}
                  >
                    <Pencil className="h-3 w-3 text-muted-foreground" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteGlossary(g); }}
                    className="p-1 rounded hover:bg-destructive/10"
                    aria-label={t('common.delete')}
                  >
                    <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                  </button>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      {/* ========== 메인 영역 ========== */}
      {selectedGlossary ? (
        <div className="flex flex-1 min-w-0">
          {/* 용어 목록 (좌측) */}
          <div className="w-[360px] shrink-0 border-r overflow-hidden">
            <TermList />
          </div>

          {/* 용어 상세 (우측) */}
          <div className="flex-1 min-w-0 flex flex-col">
            {/* 상단 액션 바 */}
            <div className="flex items-center justify-end gap-2 px-4 py-2 border-b">
              <Button
                size="sm"
                variant="outline"
                className="h-7 gap-1 text-xs"
                onClick={openImportExport}
              >
                <Download className="h-3.5 w-3.5" />
                {t('glossary.importExport.title')}
              </Button>
            </div>

            <TermDetail />
          </div>
        </div>
      ) : (
        /* 용어집 미선택 상태 */
        <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-4">
          <BookOpen className="h-12 w-12 opacity-30" />
          <h2 className="text-lg font-semibold text-foreground">
            {t('glossary.noGlossarySelected')}
          </h2>
          <p className="text-sm">{t('glossary.noGlossaryHint')}</p>
          <Button onClick={() => openGlossaryEditor()}>
            <Plus className="h-4 w-4 mr-1" />
            {t('glossary.glossary.createFirst')}
          </Button>
        </div>
      )}

      {/* ========== 다이얼로그 (포탈) ========== */}
      <TermEditor />
      <GlossaryEditorDialog />
      <GlossaryImportExport />
    </div>
  );
};
