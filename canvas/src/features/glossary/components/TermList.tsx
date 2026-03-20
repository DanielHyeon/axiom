/**
 * TermList — 용어 목록 (좌측 패널)
 * 검색, 카테고리 필터, 상태 필터, 알파벳 인덱스 제공
 */

import React, { useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, Plus, Check } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useGlossaryStore } from '../store/useGlossaryStore';
import { useTerms } from '../hooks/useGlossary';
import { CategoryManager } from './CategoryManager';
import type { GlossaryTerm, TermStatus } from '../types/glossary';

// 상태별 배지 스타일
const statusBadge: Record<TermStatus, { className: string; labelKey: string }> = {
  draft: { className: 'bg-muted text-muted-foreground', labelKey: 'glossary.status.draft' },
  approved: { className: 'bg-emerald-500/15 text-emerald-600', labelKey: 'glossary.status.approved' },
  deprecated: { className: 'bg-destructive/15 text-destructive', labelKey: 'glossary.status.deprecated' },
};

// 상태 필터 옵션
const STATUS_FILTERS: { value: TermStatus | null; labelKey: string }[] = [
  { value: null, labelKey: 'common.all' },
  { value: 'draft', labelKey: 'glossary.status.draft' },
  { value: 'approved', labelKey: 'glossary.status.approved' },
  { value: 'deprecated', labelKey: 'glossary.status.deprecated' },
];

// 알파벳 인덱스
const ALPHA_INDEX = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

export const TermList: React.FC = () => {
  const { t } = useTranslation();
  const {
    selectedGlossary,
    selectedTerm,
    searchQuery,
    statusFilter,
    categoryFilter,
    setSearchQuery,
    setStatusFilter,
    setCategoryFilter,
    setSelectedTerm,
    openTermEditor,
  } = useGlossaryStore();

  const glossaryId = selectedGlossary?.id ?? null;

  // TanStack Query로 용어 목록 가져오기
  const { data: termData, isLoading } = useTerms(glossaryId, {
    query: searchQuery || undefined,
    category: categoryFilter || undefined,
    status: statusFilter || undefined,
  });

  const terms: GlossaryTerm[] = termData?.terms ?? [];

  // 알파벳 인덱스별 그룹핑
  const groupedTerms = useMemo(() => {
    const groups: Record<string, GlossaryTerm[]> = {};
    for (const term of terms) {
      const firstChar = term.name.charAt(0).toUpperCase();
      const key = /[A-Z]/.test(firstChar) ? firstChar : '#';
      if (!groups[key]) groups[key] = [];
      groups[key].push(term);
    }
    // 각 그룹 내 이름 정렬
    for (const key of Object.keys(groups)) {
      groups[key].sort((a, b) => a.name.localeCompare(b.name));
    }
    return groups;
  }, [terms]);

  // 존재하는 알파벳만 모아서 인덱스 네비 활성화 여부 판단
  const activeLetters = useMemo(
    () => new Set(Object.keys(groupedTerms)),
    [groupedTerms],
  );

  /** 알파벳 클릭 시 해당 섹션으로 스크롤 */
  const scrollToLetter = useCallback((letter: string) => {
    const el = document.getElementById(`glossary-group-${letter}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  /** 용어 클릭 — 선택 + 상세 표시 */
  const handleTermClick = useCallback(
    (term: GlossaryTerm) => {
      setSelectedTerm(term);
    },
    [setSelectedTerm],
  );

  if (!selectedGlossary) return null;

  return (
    <div className="flex flex-col h-full">
      {/* 상단: 용어집 이름 + 새 용어 버튼 */}
      <div className="px-4 pt-4 pb-2 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold truncate">{selectedGlossary.name}</h2>
          <Button size="sm" variant="default" className="h-7 gap-1 text-xs" onClick={() => openTermEditor()}>
            <Plus className="h-3.5 w-3.5" />
            {t('glossary.term.create')}
          </Button>
        </div>

        {/* 검색 */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('glossary.search')}
            className="pl-8 h-8 text-sm"
          />
        </div>

        {/* 상태 필터 탭 */}
        <div className="flex gap-1">
          {STATUS_FILTERS.map((sf) => (
            <button
              key={sf.value ?? 'all'}
              onClick={() => setStatusFilter(sf.value)}
              className={`px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                statusFilter === sf.value
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              {t(sf.labelKey)}
            </button>
          ))}
        </div>

        {/* 카테고리 필터 */}
        <CategoryManager selectedCategory={categoryFilter} onSelect={setCategoryFilter} />
      </div>

      {/* 용어 목록 + 알파벳 인덱스 */}
      <div className="flex flex-1 min-h-0">
        {/* 알파벳 인덱스 (좌측 레일) */}
        <nav
          className="flex flex-col items-center w-6 py-1 shrink-0 overflow-y-auto"
          aria-label="Alphabetical index"
        >
          {ALPHA_INDEX.map((letter) => (
            <button
              key={letter}
              onClick={() => scrollToLetter(letter)}
              disabled={!activeLetters.has(letter)}
              className={`w-5 h-5 flex items-center justify-center text-[10px] font-medium rounded transition-colors ${
                activeLetters.has(letter)
                  ? 'text-foreground hover:bg-muted cursor-pointer'
                  : 'text-muted-foreground/30 cursor-default'
              }`}
              aria-label={`Jump to ${letter}`}
            >
              {letter}
            </button>
          ))}
        </nav>

        {/* 용어 스크롤 영역 */}
        <div className="flex-1 overflow-y-auto pr-2 pb-4">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <span className="text-sm text-muted-foreground">{t('common.loading')}</span>
            </div>
          )}

          {!isLoading && terms.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center gap-3">
              <p className="text-sm text-muted-foreground">
                {searchQuery || statusFilter || categoryFilter
                  ? t('common.noSearchResults')
                  : t('glossary.term.empty')}
              </p>
              {!searchQuery && !statusFilter && !categoryFilter && (
                <Button size="sm" onClick={() => openTermEditor()}>
                  <Plus className="h-4 w-4 mr-1" />
                  {t('glossary.term.createFirst')}
                </Button>
              )}
            </div>
          )}

          {/* 알파벳별 그룹 */}
          {ALPHA_INDEX.filter((l) => groupedTerms[l]).map((letter) => (
            <div key={letter} id={`glossary-group-${letter}`}>
              {/* 그룹 헤더 */}
              <div className="sticky top-0 z-10 px-2 py-1 text-xs font-semibold text-muted-foreground bg-background/95 backdrop-blur-sm border-b">
                {letter}
              </div>

              {/* 용어 아이템 */}
              {groupedTerms[letter].map((term) => {
                const isActive = selectedTerm?.id === term.id;
                const sb = statusBadge[term.status];
                return (
                  <button
                    key={term.id}
                    onClick={() => handleTermClick(term)}
                    className={`w-full text-left px-3 py-2.5 flex items-center gap-3 transition-colors rounded-md mx-1 ${
                      isActive
                        ? 'bg-primary/10 text-foreground'
                        : 'hover:bg-muted text-foreground/80'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{term.name}</p>
                      {term.definition && (
                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                          {term.definition}
                        </p>
                      )}
                    </div>
                    <Badge className={`${sb.className} text-[10px] px-1.5 py-0 shrink-0`}>
                      {term.status === 'approved' && <Check className="h-2.5 w-2.5 mr-0.5" />}
                      {t(sb.labelKey)}
                    </Badge>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
