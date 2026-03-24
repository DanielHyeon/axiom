/**
 * ExplorerPage — 오브젝트 드릴다운 탐색기 메인 페이지
 *
 * Weaver Object Explorer API를 이용한 검색 → 드릴다운 → 상세 보기 UI.
 *
 * 레이아웃:
 *   ┌─────────────────────────────────┬─────────────────────┐
 *   │  검색바                         │                     │
 *   ├─────────────────────────────────│   속성 상세 패널     │
 *   │  브레드크럼                     │   (PropertiesTable) │
 *   ├─────────────────────────────────│                     │
 *   │  결과 카드 그리드 / 드릴다운    │                     │
 *   │  (ObjectCard 목록)             │                     │
 *   └─────────────────────────────────┴─────────────────────┘
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Search,
  ChevronRight,
  Home,
  Loader2,
  AlertCircle,
  RefreshCw,
  X,
  Compass,
  Info,
  ArrowDownRight,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

import { useObjectExplorer } from '../hooks/useObjectExplorer';
import { ObjectCard } from './ObjectCard';
import { PropertiesTable } from './PropertiesTable';
import type { ObjectSearchResult } from '../types/explorer';

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const ExplorerPage: React.FC = () => {
  const { t } = useTranslation();
  // ── 검색어 입력 상태 ──
  const [inputValue, setInputValue] = useState('');

  // ── 오브젝트 탐색 훅 ──
  const {
    search,
    drillDown,
    goBack,
    selectItem,
    results,
    children,
    breadcrumb,
    selectedItem,
    isSearching,
    isDrilling,
    error,
    searchQuery,
    reset,
  } = useObjectExplorer();

  // ── 검색 실행 ──
  const handleSearch = useCallback(() => {
    if (inputValue.trim()) {
      search(inputValue);
    }
  }, [inputValue, search]);

  // Enter 키 핸들러
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        handleSearch();
      }
    },
    [handleSearch],
  );

  // ── 카드 클릭 → 선택 + 드릴다운 ──
  const handleCardClick = useCallback(
    (item: ObjectSearchResult) => {
      // 같은 항목 클릭 시 토글
      if (selectedItem?.id_value === item.id_value && selectedItem?.object_type === item.object_type) {
        selectItem(null);
      } else {
        selectItem(item);
      }
    },
    [selectedItem, selectItem],
  );

  // ── 드릴다운 버튼 클릭 ──
  const handleDrillDown = useCallback(
    (item: ObjectSearchResult) => {
      drillDown(item);
    },
    [drillDown],
  );

  // ── 초기화 ──
  const handleReset = useCallback(() => {
    setInputValue('');
    reset();
  }, [reset]);

  // ── 로딩 중 여부 ──
  const isLoading = isSearching || isDrilling;

  // ── 표시할 결과가 있는지 ──
  const hasResults = results.length > 0;
  const hasSearched = searchQuery.length > 0;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* ─── 페이지 헤더 ─── */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-card">
        <Compass className="h-5 w-5 text-primary" />
        <div>
          <h1 className="text-base font-semibold text-foreground">
            {t('explorerF.m6fe4f74f')}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t('explorerF.m51443782')}
          </p>
        </div>
      </div>

      {/* ─── 검색바 ─── */}
      <div className="flex items-center gap-2 px-6 py-3 border-b border-border bg-card/50">
        <div className="relative flex-1 max-w-xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('explorerExt.searchPlaceholder')}
            className="h-9 pl-9 pr-9 text-sm"
            disabled={isLoading}
          />
          {/* 입력 초기화 버튼 */}
          {inputValue && (
            <button
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => setInputValue('')}
              aria-label={t('explorerExt.clearSearch')}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* 검색 버튼 */}
        <Button
          onClick={handleSearch}
          disabled={!inputValue.trim() || isLoading}
          size="sm"
          className="h-9 px-4"
        >
          {isSearching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          <span className="ml-1.5">{t('objectExplorerExt.searchTab')}</span>
        </Button>

        {/* 초기화 버튼 */}
        {hasSearched && (
          <Button
            variant="outline"
            size="sm"
            className="h-9"
            onClick={handleReset}
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            {t('objectExplorerExt.reset')}
          </Button>
        )}
      </div>

      {/* ─── 브레드크럼 ─── */}
      {breadcrumb.length > 0 && (
        <div className="flex items-center gap-1 px-6 py-2 border-b border-border bg-muted/30 overflow-x-auto">
          {/* 루트 (검색 결과) */}
          <button
            className="flex items-center gap-1 text-xs text-primary hover:underline shrink-0"
            onClick={() => goBack(-1)}
          >
            <Home className="h-3 w-3" />
            <span>{t('explorerExt.searchResults')}</span>
          </button>

          {/* 경로 항목 */}
          {breadcrumb.map((crumb, idx) => (
            <React.Fragment key={`${crumb.object_type}-${crumb.id_value}-${idx}`}>
              <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
              {idx < breadcrumb.length - 1 ? (
                // 클릭 가능한 중간 경로
                <button
                  className="flex items-center gap-1.5 text-xs text-primary hover:underline shrink-0"
                  onClick={() => goBack(idx)}
                >
                  <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                    {crumb.object_type}
                  </Badge>
                  <span className="max-w-[120px] truncate">{crumb.name_value}</span>
                </button>
              ) : (
                // 현재 위치 (클릭 불가)
                <span className="flex items-center gap-1.5 text-xs text-foreground font-medium shrink-0">
                  <Badge variant="secondary" className="text-[9px] px-1.5 py-0">
                    {crumb.object_type}
                  </Badge>
                  <span className="max-w-[120px] truncate">{crumb.name_value}</span>
                </span>
              )}
            </React.Fragment>
          ))}
        </div>
      )}

      {/* ─── 메인 콘텐츠 영역 (결과 + 상세) ─── */}
      <div className="flex flex-1 min-h-0">
        {/* ── 좌측: 결과 목록 ── */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border">
          {/* 결과 헤더 */}
          {hasSearched && (
            <div className="flex items-center justify-between px-6 py-2 border-b border-border bg-muted/20">
              <span className="text-xs text-muted-foreground">
                {breadcrumb.length > 0 ? (
                  <>
                    <span className="font-medium text-foreground">
                      {breadcrumb[breadcrumb.length - 1].name_value}
                    </span>
                    {t('explorerF.mdf5327f3')}
                  </>
                ) : (
                  <>
                    <span className="font-medium text-foreground">"{searchQuery}"</span>
                    {' '}{t('explorerF.searchResults')}
                  </>
                )}
              </span>
              <Badge variant="secondary" className="text-[10px]">
                {t('explorerF.resultCount', { count: results.length })}
              </Badge>
            </div>
          )}

          {/* 결과 스크롤 영역 */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {/* 초기 상태: 검색 전 */}
            {!hasSearched && !isLoading && (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                <Search className="h-12 w-12 text-muted-foreground/30" />
                <div className="text-center">
                  <p className="text-sm font-medium">{t('explorerExt.searchPrompt')}</p>
                  <p className="text-xs mt-1">
                    {t('explorerF.m324b47cf')}
                  </p>
                </div>
              </div>
            )}

            {/* 로딩 상태 */}
            {isLoading && (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <Loader2 className="h-8 w-8 text-primary animate-spin" />
                <span className="text-xs text-muted-foreground">
                  {isSearching ? t('explorerExt.searching') : t('explorerExt.drilldownLoading')}
                </span>
              </div>
            )}

            {/* 에러 상태 */}
            {!isLoading && error && (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <AlertCircle className="h-8 w-8 text-destructive" />
                <p className="text-sm text-destructive font-medium">{error}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSearch}
                >
                  <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                  {t('datasource.erd.retryBtn')}
                </Button>
              </div>
            )}

            {/* 빈 결과 */}
            {!isLoading && !error && hasSearched && !hasResults && (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                <Search className="h-8 w-8 text-muted-foreground/40" />
                <div className="text-center">
                  <p className="text-sm font-medium">{t('explorerExt.noResults')}</p>
                  <p className="text-xs mt-1">
                    {t('explorerF.mae814bed')}
                  </p>
                </div>
              </div>
            )}

            {/* 결과 카드 그리드 */}
            {!isLoading && !error && hasResults && (
              <div className="space-y-2">
                {/* 자식 그룹이 있으면 그룹별로 표시 */}
                {children.length > 0 ? (
                  children.map((group) => (
                    <div key={group.object_type} className="mb-4">
                      {/* 그룹 헤더 */}
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="outline" className="text-[10px]">
                          {group.object_type}
                        </Badge>
                        <span className="text-[11px] text-muted-foreground">
                          {t('explorerF.resultCount', { count: group.count })}
                        </span>
                      </div>
                      {/* 그룹 내 카드 */}
                      <div className="space-y-1.5">
                        {group.items.map((item) => (
                          <div
                            key={`${item.object_type}-${item.id_value}`}
                            className="flex items-center gap-1"
                          >
                            <div className="flex-1 min-w-0">
                              <ObjectCard
                                item={item}
                                onClick={handleCardClick}
                                isSelected={
                                  selectedItem?.id_value === item.id_value &&
                                  selectedItem?.object_type === item.object_type
                                }
                              />
                            </div>
                            {/* 드릴다운 버튼 */}
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 shrink-0"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDrillDown(item);
                              }}
                              title={t('explorerExt.viewChildren')}
                            >
                              <ArrowDownRight className="h-4 w-4 text-muted-foreground hover:text-primary" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                ) : (
                  /* 검색 결과 (그룹 없이 평면) */
                  <div className="space-y-1.5">
                    {results.map((item) => (
                      <div
                        key={`${item.object_type}-${item.id_value}`}
                        className="flex items-center gap-1"
                      >
                        <div className="flex-1 min-w-0">
                          <ObjectCard
                            item={item}
                            onClick={handleCardClick}
                            isSelected={
                              selectedItem?.id_value === item.id_value &&
                              selectedItem?.object_type === item.object_type
                            }
                          />
                        </div>
                        {/* 드릴다운 버튼 */}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDrillDown(item);
                          }}
                          title={t('explorerExt.viewChildren')}
                        >
                          <ArrowDownRight className="h-4 w-4 text-muted-foreground hover:text-primary" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── 우측: 속성 상세 패널 ── */}
        <div className="w-[360px] shrink-0 flex flex-col bg-card">
          {selectedItem ? (
            <>
              {/* 상세 헤더 */}
              <div className="flex items-start justify-between px-4 py-3 border-b border-border bg-muted/30">
                <div className="flex flex-col gap-1.5 min-w-0">
                  <Badge
                    variant="secondary"
                    className="text-[10px] w-fit px-2 py-0.5"
                  >
                    {selectedItem.object_type}
                  </Badge>
                  <h3 className="text-sm font-semibold text-foreground break-words">
                    {selectedItem.name_value || selectedItem.id_value}
                  </h3>
                  {selectedItem.name_value && selectedItem.id_value && (
                    <p className="text-xs text-muted-foreground">
                      ID: {selectedItem.id_value}
                    </p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  onClick={() => selectItem(null)}
                  aria-label={t('explorerExt.closeDetail')}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>

              {/* 속성 테이블 */}
              <div className="flex-1 overflow-y-auto p-4">
                <div className="flex items-center gap-1.5 mb-3">
                  <Info className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {t('explorerF.propertyCount', { count: Object.keys(selectedItem.properties).length })}
                  </span>
                </div>
                <PropertiesTable properties={selectedItem.properties} />

                {/* 드릴다운 액션 */}
                <div className="mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => handleDrillDown(selectedItem)}
                    disabled={isDrilling}
                  >
                    {isDrilling ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    ) : (
                      <ArrowDownRight className="h-3.5 w-3.5 mr-1.5" />
                    )}
                    {t('explorerF.mc998b79b')}
                  </Button>
                </div>
              </div>
            </>
          ) : (
            /* 미선택 상태 */
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2 px-6">
              <Info className="h-8 w-8 text-muted-foreground/30" />
              <p className="text-xs text-center">
                {t('explorerF.m27942ff2')}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
