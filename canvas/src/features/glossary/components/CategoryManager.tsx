/**
 * CategoryManager — 카테고리 CRUD (태그 형태 관리)
 * 글로서리 용어에 부여할 카테고리를 생성/삭제하는 팝오버
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, X, Tag } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useCategories, useCreateCategory, useDeleteCategory } from '../hooks/useGlossary';
import type { GlossaryCategory } from '../types/glossary';

// 카테고리 기본 색상 팔레트
const CATEGORY_COLORS = [
  '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b',
  '#ef4444', '#ec4899', '#06b6d4', '#84cc16',
];

interface CategoryManagerProps {
  /** 현재 선택된 카테고리 (필터 용도) */
  selectedCategory: string | null;
  /** 카테고리 선택 시 콜백 */
  onSelect: (category: string | null) => void;
}

export const CategoryManager: React.FC<CategoryManagerProps> = ({
  selectedCategory,
  onSelect,
}) => {
  const { t } = useTranslation();
  const [newName, setNewName] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const { data: categoryData, isLoading } = useCategories();
  const createMut = useCreateCategory();
  const deleteMut = useDeleteCategory();

  const categories: GlossaryCategory[] = categoryData?.categories ?? [];

  /** 카테고리 생성 */
  const handleCreate = useCallback(() => {
    const trimmed = newName.trim();
    if (!trimmed) return;
    // 랜덤 색상 할당
    const color = CATEGORY_COLORS[categories.length % CATEGORY_COLORS.length];
    createMut.mutate({ name: trimmed, color }, {
      onSuccess: () => {
        setNewName('');
        setIsAdding(false);
      },
    });
  }, [newName, categories.length, createMut]);

  /** 카테고리 삭제 */
  const handleDelete = useCallback(
    (cat: GlossaryCategory) => {
      if (!window.confirm(t('glossary.category.confirmDelete', { name: cat.name }))) return;
      deleteMut.mutate(cat.id, {
        onSuccess: () => {
          // 삭제된 카테고리가 현재 필터면 해제
          if (selectedCategory === cat.name) onSelect(null);
        },
      });
    },
    [deleteMut, selectedCategory, onSelect, t],
  );

  return (
    <div className="flex flex-col gap-2">
      {/* 카테고리 태그 목록 */}
      <div className="flex flex-wrap gap-1.5">
        {/* "전체" 버튼 */}
        <button
          onClick={() => onSelect(null)}
          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer border ${
            selectedCategory === null
              ? 'bg-primary text-primary-foreground border-primary'
              : 'bg-muted text-muted-foreground border-transparent hover:bg-muted/80'
          }`}
        >
          {t('common.all')}
        </button>

        {isLoading && (
          <span className="text-xs text-muted-foreground px-2 py-1">
            {t('common.loading')}
          </span>
        )}

        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => onSelect(selectedCategory === cat.name ? null : cat.name)}
            className={`group inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer border ${
              selectedCategory === cat.name
                ? 'border-primary text-primary-foreground'
                : 'border-transparent text-foreground/70 hover:bg-muted/80'
            }`}
            style={{
              backgroundColor:
                selectedCategory === cat.name ? cat.color : `${cat.color}20`,
            }}
          >
            <Tag className="h-3 w-3" />
            {cat.name}
            <Badge variant="secondary" className="ml-0.5 h-4 px-1 text-[10px]">
              {cat.termCount}
            </Badge>
            {/* 삭제 버튼 — hover 시 표시 */}
            <span
              role="button"
              tabIndex={0}
              aria-label={t('common.delete')}
              onClick={(e) => {
                e.stopPropagation();
                handleDelete(cat);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.stopPropagation(); handleDelete(cat); }
              }}
              className="hidden group-hover:inline-flex items-center ml-0.5 hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </span>
          </button>
        ))}
      </div>

      {/* 카테고리 추가 인라인 폼 */}
      {isAdding ? (
        <div className="flex items-center gap-1.5">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleCreate();
              if (e.key === 'Escape') { setIsAdding(false); setNewName(''); }
            }}
            placeholder={t('glossary.category.placeholder')}
            className="h-7 text-xs"
            autoFocus
          />
          <Button size="sm" variant="ghost" className="h-7 px-2" onClick={handleCreate}>
            <Plus className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2"
            onClick={() => { setIsAdding(false); setNewName(''); }}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ) : (
        <button
          onClick={() => setIsAdding(true)}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <Plus className="h-3 w-3" />
          {t('glossary.category.add')}
        </button>
      )}
    </div>
  );
};
