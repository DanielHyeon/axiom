/**
 * 대시보드 메인 페이지 — .pen 디자인 사양에 맞춘 리디자인.
 *
 * 레이아웃: 풀 너비 수직 스택
 * - 상단: 통계 카드 4장 (가로 동일 폭, 16px 간격)
 * - 하단: 좌측 Recent Cases 테이블 (유동 폭) + 우측 Activity 타임라인 (280px)
 *
 * 데이터 소스: Core 서비스 실 API (useCases, useCaseActivities)
 * 에러/로딩/빈 상태 모두 처리.
 */
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import { useCaseActivities } from '@/features/case-dashboard/hooks/useCaseActivities';
import { useCaseStats } from '@/features/case-dashboard/hooks/useCaseStats';
import { ErrorState } from '@/shared/components/ErrorState';
import { ROUTES } from '@/lib/routes/routes';
import { FolderOpen, Clock } from 'lucide-react';

/* ────────────────────────────────────────────────────────────
   타입 정의
   ──────────────────────────────────────────────────────────── */

/** 통계 카드 하나에 필요한 정보 */
interface StatCardDef {
  label: string;
  value: string;
  change: string;
  /** 변화 텍스트 색상: green(증가 긍정), red(감소 부정), blue(정보), orange(보류) */
  changeColor: 'green' | 'red' | 'blue' | 'orange';
}

/** 케이스 상태 → 배지 스타일 매핑 */
const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  IN_PROGRESS: {
    label: 'Active',
    cls: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  },
  PENDING: {
    label: 'Pending',
    cls: 'bg-amber-50 text-amber-700 border border-amber-200',
  },
  COMPLETED: {
    label: 'Resolved',
    cls: 'bg-slate-100 text-slate-600 border border-slate-200',
  },
  REJECTED: {
    label: 'Rejected',
    cls: 'bg-red-50 text-red-700 border border-red-200',
  },
};

/* ────────────────────────────────────────────────────────────
   유틸 함수
   ──────────────────────────────────────────────────────────── */

/** 숫자를 콤마 표기 문자열로 변환 */
function fmt(n: number): string {
  return n.toLocaleString('en-US');
}

/** ISO 타임스탬프를 "3h ago", "2d ago" 등 상대 시간으로 변환 */
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/* ────────────────────────────────────────────────────────────
   서브 컴포넌트
   ──────────────────────────────────────────────────────────── */

/** 통계 카드 — .pen 사양: 흰색 bg, 12px radius, 1px border, 20px padding */
function StatCard({ label, value, change, changeColor }: StatCardDef) {
  const colorMap: Record<string, string> = {
    green: 'text-emerald-600',
    red: 'text-red-600',
    blue: 'text-blue-600',
    orange: 'text-amber-600',
  };

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-5">
      {/* 라벨: Geist 12px, medium 500, #5E5E5E */}
      <span className="text-[12px] font-medium text-text-secondary font-secondary">
        {label}
      </span>
      {/* 값: Sora 28px, bold 700, #000000, letterSpacing -1px */}
      <span className="text-[28px] font-bold tracking-[-1px] text-text-primary font-heading leading-none">
        {value}
      </span>
      {/* 변화: Geist 11px, 색상 분기 */}
      <span className={`text-[11px] font-secondary ${colorMap[changeColor]}`}>
        {change}
      </span>
    </div>
  );
}

/** 통계 행 스켈레톤 — 카드 4개 placeholder */
function StatsRowSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true" aria-label="Loading stats">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5">
          <div className="h-3 w-20 rounded bg-secondary animate-pulse" />
          <div className="h-7 w-16 rounded bg-secondary animate-pulse" />
          <div className="h-3 w-28 rounded bg-secondary animate-pulse" />
        </div>
      ))}
    </div>
  );
}

/** 테이블 스켈레톤 — 5행 placeholder */
function TableSkeleton() {
  return (
    <div className="space-y-0" aria-busy="true" aria-label="Loading cases">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 h-[44px] px-5 border-b border-border">
          <div className="h-3 w-[80px] rounded bg-secondary animate-pulse" />
          <div className="h-3 flex-1 max-w-[240px] rounded bg-secondary animate-pulse" />
          <div className="h-5 w-[72px] rounded-full bg-secondary animate-pulse" />
          <div className="h-3 w-[72px] rounded bg-secondary animate-pulse" />
        </div>
      ))}
    </div>
  );
}

/** 타임라인 스켈레톤 */
function TimelineSkeleton() {
  return (
    <div className="space-y-4 p-3" aria-busy="true" aria-label="Loading activity">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex items-start gap-2.5">
          <div className="mt-1 size-2 shrink-0 rounded-full bg-secondary animate-pulse" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 w-3/4 rounded bg-secondary animate-pulse" />
            <div className="h-2.5 w-1/3 rounded bg-secondary animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   메인 페이지 컴포넌트
   ──────────────────────────────────────────────────────────── */

export function CaseDashboardPage() {
  /* ── 데이터 페칭 (TanStack Query 기반 기존 훅 재사용) ── */
  const {
    data: cases,
    isLoading: casesLoading,
    error: casesError,
    refetch: refetchCases,
  } = useCases({ limit: 20 });

  const {
    data: activities = [],
    isLoading: activitiesLoading,
  } = useCaseActivities({ limit: 10 });

  /* ── 통계 계산 (기존 useCaseStats 훅 활용) — items 배열 전달 ── */
  const stats = useCaseStats(cases?.items);
  /* 서버가 반환하는 전체 건수 (loaded items.length가 아닌 실제 total) */
  const serverTotal = cases?.total ?? 0;

  /* ── 통계 카드 데이터 (API 실 데이터 기반, 트렌드 API 미구현으로 placeholder 표시) ── */
  const statCards: StatCardDef[] = useMemo(
    () => [
      {
        label: 'Total Cases',
        // 서버 total 사용 — loaded items.length(최대 20건)가 아닌 실제 전체 건수
        value: fmt(serverTotal),
        change: '\u2014', // 트렌드 API 미연동 — placeholder
        changeColor: 'blue',
      },
      {
        label: 'Active',
        value: fmt(stats.inProgress),
        change: `${serverTotal > 0 ? Math.round((stats.inProgress / serverTotal) * 100) : 0}% of loaded`,
        changeColor: 'blue',
      },
      {
        label: 'Pending Review',
        value: fmt(stats.inReview),
        change: '\u2014', // 트렌드 API 미연동 — placeholder
        changeColor: 'orange',
      },
      {
        label: 'Resolved',
        value: fmt(stats.total - stats.inProgress - stats.inReview),
        change: '\u2014', // 트렌드 API 미연동 — placeholder
        changeColor: 'green',
      },
    ],
    [stats, serverTotal],
  );

  /* ── 최근 케이스 (테이블에 표시할 최대 8건) ── */
  const recentCases = useMemo(() => (cases?.items ?? []).slice(0, 8), [cases]);

  /* ── 타임라인 색상 순환 (dot 색상) ── */
  const dotColors = ['bg-emerald-500', 'bg-blue-500', 'bg-amber-500', 'bg-red-500', 'bg-violet-500'];

  /* ── 전체 에러 상태 ── */
  if (casesError) {
    return (
      <div className="py-8 px-12">
        <ErrorState
          message={`Failed to load dashboard data: ${casesError.message}`}
          onRetry={refetchCases}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 py-8 px-12">
      {/* ━━━ 1. 상단 통계 카드 4장 ━━━ */}
      {casesLoading ? (
        <StatsRowSkeleton />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {statCards.map((card) => (
            <StatCard key={card.label} {...card} />
          ))}
        </div>
      )}

      {/* ━━━ 2. 하단: 좌측 테이블 + 우측 타임라인 ━━━ */}
      <div className="flex gap-6 min-h-0 flex-1">
        {/* ── 좌측: Recent Cases 테이블 ── */}
        <div className="flex flex-col flex-1 min-w-0 rounded-xl border border-border bg-card overflow-hidden">
          {/* 헤더: 48px 높이 */}
          <div className="flex items-center justify-between h-12 px-5 shrink-0">
            <h2 className="text-[13px] font-semibold text-foreground font-heading">
              Recent Cases
            </h2>
            <Link
              to={ROUTES.CASES.LIST}
              className="text-[13px] font-medium text-primary hover:text-primary/80 transition-colors"
            >
              View All &rarr;
            </Link>
          </div>

          {/* 컬럼 헤더: 36px, bg #F5F5F5 */}
          <div
            className="grid shrink-0 items-center h-9 px-5 bg-muted text-[11px] font-semibold text-text-secondary font-secondary uppercase tracking-wide grid-cols-[100px_1fr_100px_100px]"
          >
            <span>Case ID</span>
            <span>Title</span>
            <span>Status</span>
            <span>Updated</span>
          </div>

          {/* 테이블 본문 — 스크롤 가능 */}
          <div className="flex-1 overflow-y-auto">
            {casesLoading ? (
              <TableSkeleton />
            ) : recentCases.length === 0 ? (
              /* 빈 상태 */
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-muted">
                  <FolderOpen className="size-5 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">No cases found</p>
                <p className="mt-1 text-xs text-text-secondary">
                  Cases will appear here once created.
                </p>
              </div>
            ) : (
              recentCases.map((c) => {
                const badge = STATUS_BADGE[c.status] ?? {
                  label: c.status,
                  cls: 'bg-slate-100 text-slate-600 border border-slate-200',
                };

                return (
                  <div
                    key={c.id}
                    className="grid items-center h-[44px] px-5 border-b border-border hover:bg-muted/30 transition-colors grid-cols-[100px_1fr_100px_100px]"
                  >
                    {/* Case ID: 파란색, JetBrains Mono 12px */}
                    <Link
                      to={ROUTES.CASES.DETAIL(c.id)}
                      className="text-[12px] font-mono text-blue-600 hover:text-blue-700 hover:underline truncate"
                    >
                      {c.id.length > 10 ? `${c.id.slice(0, 10)}...` : c.id}
                    </Link>

                    {/* Title: Geist 12px, 기본 텍스트 */}
                    <span className="text-[12px] font-secondary text-foreground truncate pr-4">
                      {c.title}
                    </span>

                    {/* Status: 색상 배지 */}
                    <span
                      className={`inline-flex items-center justify-center h-[22px] w-fit px-2.5 rounded-full text-[11px] font-medium ${badge.cls}`}
                    >
                      {badge.label}
                    </span>

                    {/* Updated: Geist 12px, 보조 텍스트 */}
                    <span className="text-[12px] font-secondary text-text-secondary">
                      {relativeTime(c.createdAt)}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── 우측: Activity Timeline (280px 고정 너비) ── */}
        <div className="flex flex-col w-[280px] shrink-0 rounded-xl border border-border bg-card overflow-hidden">
          {/* 헤더: 48px */}
          <div className="flex items-center h-12 px-5 shrink-0">
            <h2 className="text-[13px] font-semibold text-foreground font-heading">
              Activity
            </h2>
          </div>

          {/* 이벤트 목록: 세로 스택, 16px 간격, 12px 패딩 */}
          <div className="flex-1 overflow-y-auto px-3 py-3">
            {activitiesLoading ? (
              <TimelineSkeleton />
            ) : activities.length === 0 ? (
              /* 빈 상태 */
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-muted">
                  <Clock className="size-4 text-muted-foreground" />
                </div>
                <p className="text-xs text-muted-foreground">No recent activity</p>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {activities.map((item, idx) => (
                  <div key={item.id} className="flex items-start gap-2.5">
                    {/* 색상 도트: 8px 원형 */}
                    <div
                      className={`mt-1.5 size-2 shrink-0 rounded-full ${dotColors[idx % dotColors.length]}`}
                    />
                    {/* 정보: title + time */}
                    <div className="flex flex-col min-w-0">
                      <span className="text-[12px] font-secondary text-foreground leading-snug line-clamp-2">
                        {item.text}
                      </span>
                      <span className="text-[11px] font-secondary text-text-secondary mt-0.5">
                        {item.time}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
