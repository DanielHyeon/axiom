/**
 * RootCausePanel -- 근본 원인 분석 패널.
 *
 * Insight 3-패널 레이아웃의 마지막 패널로,
 * 선택된 Driver의 근본 원인을 계층적으로 표시한다.
 * Vision RCA API 결과를 시각화한다.
 */

import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import {
  Search,
  Loader2,
  AlertTriangle,
  Layers,
  Cog,
  Users,
  Package,
  Target,
} from 'lucide-react';

// ── 타입 정의 ──

/** 근본 원인 항목 */
export interface RootCause {
  id: string;
  /** 원인 이름 */
  name: string;
  /** 기여도 (0~1) */
  contribution: number;
  /** 카테고리: process, material, machine, human 등 */
  category: string;
  /** 분석 깊이 (1=직접, 2=간접, 3=근본) */
  depth: number;
}

export interface RootCausePanelProps {
  /** 선택된 드라이버 ID (null이면 빈 상태) */
  driverId: string | null;
  /** 근본 원인 목록 */
  rootCauses: RootCause[];
  /** 로딩 중 여부 */
  isLoading: boolean;
  /** 근본 원인 선택 콜백 */
  onSelectRootCause?: (id: string) => void;
}

// ── 카테고리별 아이콘 매핑 ──
const CATEGORY_ICON: Record<string, typeof Cog> = {
  process: Layers,
  material: Package,
  machine: Cog,
  human: Users,
};

// ── 깊이별 색상 매핑 (기여도 바 색상) ──
const DEPTH_COLORS: Record<number, string> = {
  1: 'bg-red-500',    // 직접 원인
  2: 'bg-orange-400', // 간접 원인
  3: 'bg-yellow-400', // 근본 원인
};

const DEPTH_TEXT_COLORS: Record<number, string> = {
  1: 'text-red-600',
  2: 'text-orange-500',
  3: 'text-yellow-600',
};

export function RootCausePanel({
  driverId,
  rootCauses,
  isLoading,
  onSelectRootCause,
}: RootCausePanelProps) {
  const { t } = useTranslation();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // 카테고리별 그룹핑
  const grouped = useMemo(() => {
    const map = new Map<string, RootCause[]>();
    for (const rc of rootCauses) {
      const list = map.get(rc.category) ?? [];
      list.push(rc);
      map.set(rc.category, list);
    }
    // 각 그룹 내에서 기여도 높은 순 정렬
    for (const [key, list] of map) {
      map.set(
        key,
        list.sort((a, b) => b.contribution - a.contribution),
      );
    }
    return map;
  }, [rootCauses]);

  // 근본 원인 클릭 핸들러
  const handleSelect = (id: string) => {
    setSelectedId(id);
    onSelectRootCause?.(id);
  };

  // ── 로딩 스켈레톤 ──
  if (isLoading) {
    return (
      <div className="space-y-3 p-4" data-testid="root-cause-loading">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          <Search className="h-3 w-3" />
          {t('insight.rootCause.title')}
        </div>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-xs text-muted-foreground">
            {t('insight.rootCause.analyzing')}
          </span>
        </div>
        {/* 스켈레톤 바 */}
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse space-y-2">
            <div className="h-3 w-24 rounded bg-muted" />
            <div className="h-8 w-full rounded bg-muted/60" />
          </div>
        ))}
      </div>
    );
  }

  // ── 드라이버 미선택 빈 상태 ──
  if (!driverId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center" data-testid="root-cause-empty">
        <AlertTriangle className="h-6 w-6 text-muted-foreground/40 mb-2" />
        <p className="text-xs text-muted-foreground">
          {t('insight.rootCause.selectDriverHint')}
        </p>
      </div>
    );
  }

  // ── 분석 결과 없음 ──
  if (rootCauses.length === 0) {
    return (
      <div className="space-y-3 p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          <Search className="h-3 w-3" />
          {t('insight.rootCause.title')}
        </div>
        <div className="flex flex-col items-center justify-center py-8 text-center" data-testid="root-cause-no-results">
          <Target className="h-5 w-5 text-muted-foreground/40 mb-2" />
          <p className="text-xs text-muted-foreground">
            {t('insight.rootCause.noResults')}
          </p>
        </div>
      </div>
    );
  }

  // ── 카테고리별 계층 표시 ──
  return (
    <div className="space-y-4 p-4" data-testid="root-cause-panel">
      {/* 헤더 */}
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
        <Search className="h-3 w-3" />
        {t('insight.rootCause.title')}
        <span className="ml-auto text-muted-foreground normal-case font-normal">
          {t('insight.rootCause.count', { count: rootCauses.length })}
        </span>
      </div>

      {/* 깊이 범례 */}
      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
          {t('insight.rootCause.depthDirect')}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-full bg-orange-400" />
          {t('insight.rootCause.depthIndirect')}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-full bg-yellow-400" />
          {t('insight.rootCause.depthRoot')}
        </span>
      </div>

      {/* 카테고리 그룹 */}
      <div className="space-y-3 max-h-[calc(100vh-380px)] overflow-y-auto pr-1">
        {Array.from(grouped.entries()).map(([category, items]) => {
          const Icon = CATEGORY_ICON[category] ?? Layers;
          return (
            <div key={category} className="space-y-1.5">
              {/* 카테고리 헤더 */}
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-foreground/70 uppercase tracking-wide">
                <Icon className="h-3 w-3" />
                {t(`insight.rootCause.category.${category}`, { defaultValue: category })}
              </div>

              {/* 원인 항목들 */}
              {items.map((rc) => {
                const isSelected = selectedId === rc.id;
                const barColor = DEPTH_COLORS[rc.depth] ?? 'bg-gray-400';
                const textColor = DEPTH_TEXT_COLORS[rc.depth] ?? 'text-gray-500';
                const barWidth = Math.max(rc.contribution * 100, 4); // 최소 4% 너비

                return (
                  <button
                    type="button"
                    key={rc.id}
                    onClick={() => handleSelect(rc.id)}
                    className={cn(
                      'w-full rounded-md px-2.5 py-2 text-left transition-colors',
                      isSelected
                        ? 'bg-primary/10 border border-primary/30'
                        : 'hover:bg-muted/50 border border-transparent',
                    )}
                    aria-label={rc.name}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-foreground truncate flex-1 mr-2">
                        {rc.name}
                      </span>
                      <span
                        className={cn(
                          'shrink-0 text-[10px] font-mono font-semibold',
                          textColor,
                        )}
                      >
                        {(rc.contribution * 100).toFixed(1)}%
                      </span>
                    </div>

                    {/* 기여도 바 */}
                    <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all', barColor)}
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>

                    {/* 깊이 레이블 */}
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      {t(`insight.rootCause.depth${rc.depth}`, {
                        defaultValue:
                          rc.depth === 1
                            ? t('insight.rootCause.depthDirect')
                            : rc.depth === 2
                              ? t('insight.rootCause.depthIndirect')
                              : t('insight.rootCause.depthRoot'),
                      })}
                    </div>
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
