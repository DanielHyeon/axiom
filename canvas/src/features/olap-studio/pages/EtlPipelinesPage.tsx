/**
 * EtlPipelinesPage — ETL 파이프라인 관리 (디자인 리뉴얼)
 *
 * .pen 디자인 매칭:
 * - 수직 레이아웃, 24px 상하 패딩, 48px 좌우, 16px 갭
 * - 파이프라인 카드: 가로 fill, 흰 배경, 12px radius, 20px 패딩, 16px 갭
 *   - 활성(선택) 파이프라인: 2px primary(#FF8400) border
 *   - 아이콘: 40x40, 컬러 배경, 8px radius
 *   - 정보 열: 이름 Geist 14px medium + 설명 Geist 11px
 *   - 상태 배지: Success=초록, Failed=빨강
 *
 * 백엔드 연동: 기존 olapStudioApi.ts etlPipelines 재사용
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, X, Loader2 } from 'lucide-react';
import { etlPipelines, type ETLPipeline, type ETLRun } from '../api/olapStudioApi';
import { useTranslation } from 'react-i18next';

// ── 상태별 스타일 매핑 (디자인 기준: Success=초록, Failed=빨강) ──

interface StatusStyle {
  /** 아이콘 배경색 */
  iconBg: string;
  /** 아이콘 색상 */
  iconColor: string;
  /** 배지 배경색 */
  badgeBg: string;
  /** 배지 텍스트색 */
  badgeColor: string;
  /** 표시 텍스트 */
  label: string;
  /** 아이콘 컴포넌트 */
  Icon: React.ElementType;
}

/** 파이프라인 status → 표시 스타일 */
function getStatusStyle(status: string): StatusStyle {
  const s = status.toUpperCase();
  if (s === 'DEPLOYED' || s === 'READY' || s === 'SUCCEEDED') {
    // 성공 — 다크모드 대응 CSS 변수 사용
    return {
      iconBg: 'hsl(var(--status-success))',
      iconColor: 'hsl(var(--status-success-foreground))',
      badgeBg: 'hsl(var(--status-success))',
      badgeColor: 'hsl(var(--status-success-foreground))',
      label: 'Success',
      Icon: Play,
    };
  }
  if (s === 'ERROR' || s === 'FAILED') {
    // 에러 — 다크모드 대응 CSS 변수 사용
    return {
      iconBg: 'hsl(var(--status-error))',
      iconColor: 'hsl(var(--status-error-foreground))',
      badgeBg: 'hsl(var(--status-error))',
      badgeColor: 'hsl(var(--status-error-foreground))',
      label: 'Failed',
      Icon: X,
    };
  }
  // 기본(DRAFT, RUNNING 등) — 다크모드 대응 CSS 변수 사용
  return {
    iconBg: 'hsl(var(--bg-surface))',
    iconColor: 'hsl(var(--text-secondary))',
    badgeBg: 'hsl(var(--bg-surface))',
    badgeColor: 'hsl(var(--text-secondary))',
    label: status,
    Icon: Play,
  };
}

export function EtlPipelinesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  // 선택된 (활성) 파이프라인 ID
  const [activeId, setActiveId] = useState<string | null>(null);

  // 파이프라인 목록 조회
  const { data: pipelines = [], isLoading } = useQuery({
    queryKey: ['olap', 'etl-pipelines'],
    queryFn: etlPipelines.list,
  });

  // 수동 실행
  const runMut = useMutation({
    mutationFn: etlPipelines.run,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['olap', 'etl-pipelines'] });
    },
  });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 본문 — 24px 상하, 48px 좌우, 16px 갭 */}
      <div className="flex flex-col flex-1 min-h-0 gap-4 px-12 py-6 overflow-y-auto">
        {/* 로딩 상태 */}
        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-5 w-5 animate-spin text-text-placeholder" />
          </div>
        )}

        {/* 빈 상태 */}
        {!isLoading && pipelines.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <p className="text-sm text-text-placeholder">
              {t('olapStudioExt.noPipelines', '등록된 파이프라인이 없습니다.')}
            </p>
          </div>
        )}

        {/* 파이프라인 카드 목록 */}
        {pipelines.map((pl) => {
          const isActive = activeId === pl.id;
          const style = getStatusStyle(pl.status);
          const IconComp = style.Icon;

          return (
            <button
              type="button"
              key={pl.id}
              onClick={() => setActiveId(isActive ? null : pl.id)}
              className={[
                'flex items-center gap-4 w-full rounded-xl bg-white p-5 text-left transition-all',
                isActive
                  ? 'border-2 border-primary'
                  : 'border border-border hover:border-muted-foreground',
              ].join(' ')}
            >
              {/* 아이콘 — 40x40, 컬러 배경, 8px radius */}
              <div
                className="flex items-center justify-center w-10 h-10 rounded-lg shrink-0"
                style={{ backgroundColor: style.iconBg }}
              >
                <IconComp
                  className="h-4 w-4"
                  style={{ color: style.iconColor }}
                />
              </div>

              {/* 정보 열 — 이름 + 설명 */}
              <div className="flex flex-col gap-0.5 flex-1 min-w-0">
                {/* 이름 — Geist 14px medium */}
                <span className="text-sm font-medium text-foreground truncate">
                  {pl.name}
                </span>
                {/* 설명 — Geist 11px secondary */}
                {pl.description && (
                  <span className="text-[11px] text-text-secondary truncate">
                    {pl.description}
                  </span>
                )}
              </div>

              {/* 상태 배지 */}
              <div
                className="shrink-0 rounded px-2.5 py-1"
                style={{ backgroundColor: style.badgeBg }}
              >
                <span
                  className="text-[10px] font-semibold"
                  style={{ color: style.badgeColor }}
                >
                  {style.label}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
