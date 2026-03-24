/**
 * ObjectCard — 오브젝트 검색 결과 카드
 *
 * 검색 결과의 개별 항목을 카드 형태로 표시한다.
 * 클릭하면 드릴다운 또는 상세 보기를 트리거한다.
 *
 * 표시 정보:
 *   - object_type : 배지 (유형 분류)
 *   - name_value  : 제목 (메인 표시명)
 *   - id_value    : 부제 (식별 값)
 */

import React from 'react';
import { ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ObjectSearchResult } from '../types/explorer';
import { useTranslation } from 'react-i18next';

// ──────────────────────────────────────
// 유형별 배지 색상 매핑
// ──────────────────────────────────────

const TYPE_BADGE_VARIANTS: Record<string, string> = {
  {t('explorerF.m5345fab1')}
  {t('explorerF.m2b2d9f12')}
  {t('explorerF.m206c0f4f')}
  {t('explorerF.m55e9dc2b')}
  {t('explorerF.mdd4d7357')}
  {t('explorerF.m9047cc06')}
};

/** 유형에 따른 배지 스타일 반환 */
function getBadgeStyle(objectType: string): string {
  return (
    TYPE_BADGE_VARIANTS[objectType] ??
    'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200'
  );
}

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface ObjectCardProps {
  /** 오브젝트 데이터 */
  item: ObjectSearchResult;
  /** 카드 클릭 콜백 (드릴다운) */
  onClick: (item: ObjectSearchResult) => void;
  /** 선택 상태 */
  isSelected?: boolean;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const ObjectCard: React.FC<ObjectCardProps> = ({
  item,
  onClick,
  isSelected = false,
}) => {
  const { t } = useTranslation();
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${item.object_type}: ${item.name_value}`}
      className={cn(
        'group flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-all',
        'hover:border-primary/60 hover:bg-primary/5 hover:shadow-sm',
        isSelected
          ? 'border-primary bg-primary/5 shadow-sm'
          : 'border-border bg-card',
      )}
      onClick={() => onClick(item)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick(item);
        }
      }}
    >
      {/* 유형 배지 */}
      <Badge
        variant="secondary"
        className={cn('text-[10px] px-2 py-0.5 shrink-0 font-medium', getBadgeStyle(item.object_type))}
      >
        {item.object_type}
      </Badge>

      {/* 이름 + ID */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-foreground truncate">
          {item.name_value || item.id_value}
        </div>
        {item.name_value && item.id_value && (
          <div className="text-xs text-muted-foreground truncate mt-0.5">
            ID: {item.id_value}
          </div>
        )}
      </div>

      {/* 드릴다운 화살표 */}
      <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary shrink-0 transition-colors" />
    </div>
  );
};
