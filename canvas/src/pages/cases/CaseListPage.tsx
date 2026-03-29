/**
 * 케이스 목록 페이지 — axiom.pen 디자인 시스템 정렬.
 *
 * 레이아웃: vertical stack, 24px padding-top, 48px padding-sides, 16px gap
 * 필터 행: 검색(280px) + 상태 드롭다운 + 건수 표시
 * 테이블: 흰색 카드, Case ID(파란색 링크) / Title / Assignee / Status(뱃지) / Priority(컬러 텍스트) / Updated
 */
import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Search, ChevronDown } from 'lucide-react';
import { ROUTES } from '@/lib/routes/routes';
import { useCases } from '@/features/case-dashboard/hooks/useCases';
import type { Case } from '@/features/case-dashboard/hooks/useCases';

/* ── 상태 뱃지 색상 설정 ── */
const STATUS_BADGE: Record<string, { label: string; bg: string; text: string; border: string }> = {
  PENDING: { label: '대기', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  IN_PROGRESS: { label: '진행 중', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  COMPLETED: { label: '완료', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  REJECTED: { label: '반려', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

/* ── 우선순위 텍스트 색상 ── */
const PRIORITY_COLOR: Record<string, string> = {
  CRITICAL: 'text-red-600 font-semibold',
  HIGH: 'text-red-500',
  MEDIUM: 'text-orange-500',
  LOW: 'text-neutral-400',
};

/* ── 상대 시간 포맷 (예: "2시간 전", "3일 전") ── */
function relativeTime(dateStr?: string): string {
  if (!dateStr) return '-';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return '방금';
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}일 전`;
  return new Date(dateStr).toLocaleDateString('ko-KR');
}

/* ── 상태 필터 옵션 ── */
type StatusFilter = '' | 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED';
const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: '', label: 'All Status' },
  { value: 'PENDING', label: '대기' },
  { value: 'IN_PROGRESS', label: '진행 중' },
  { value: 'COMPLETED', label: '완료' },
  { value: 'REJECTED', label: '반려' },
];

export const CaseListPage: React.FC = () => {
  /* 검색어는 디바운스 적용 — 입력값과 실제 쿼리 분리 */
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('');

  /* 디바운스 타이머 — useRef로 리렌더 간 타이머 유지 */
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = (val: string) => {
    setSearchInput(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearchQuery(val), 300);
  };

  /* 서버 측 필터링 — status와 search를 API에 전달 */
  const { data, isLoading, error } = useCases({
    status: statusFilter || undefined,
    search: searchQuery || undefined,
    limit: 100,
  });

  const cases = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="flex flex-col pt-6 px-12 gap-4 h-full">
      {/* ── 필터 행 ── */}
      <div className="flex items-center gap-3">
        {/* 검색 입력 */}
        <div className="relative w-[280px]">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400"
            aria-hidden
          />
          <input
            type="search"
            placeholder="Search cases..."
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full h-9 pl-9 pr-3 text-xs bg-white border border-neutral-200 rounded-md outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 placeholder:text-neutral-400"
            aria-label="케이스 검색"
          />
        </div>

        {/* 상태 드롭다운 */}
        <div className="relative">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="appearance-none h-9 pl-3 pr-8 text-xs bg-white border border-neutral-200 rounded-md outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 cursor-pointer"
            aria-label="상태 필터"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown
            className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-neutral-400 pointer-events-none"
            aria-hidden
          />
        </div>

        {/* 건수 표시 */}
        <span className="text-xs text-neutral-400 ml-auto tabular-nums">
          {total.toLocaleString()} cases
        </span>
      </div>

      {/* ── 에러 상태 ── */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600">
          케이스를 불러오는 중 오류가 발생했습니다. 새로고침해 주세요.
        </div>
      )}

      {/* ── 테이블 카드 ── */}
      <div className="flex-1 min-h-0 bg-white border border-neutral-200 rounded-xl overflow-hidden">
        <div className="h-full overflow-auto">
          <table className="w-full text-left">
            {/* 헤더 */}
            <thead className="sticky top-0 z-10">
              <tr className="bg-neutral-50 border-b border-neutral-200">
                <th className="w-[90px] px-4 h-10 text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                  Case ID
                </th>
                <th className="px-4 h-10 text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                  Title
                </th>
                <th className="w-[120px] px-4 h-10 text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                  Assignee
                </th>
                <th className="w-[100px] px-4 h-10 text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="w-[80px] px-4 h-10 text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                  Priority
                </th>
                <th className="w-[90px] px-4 h-10 text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                  Updated
                </th>
              </tr>
            </thead>

            <tbody>
              {/* 로딩 스켈레톤 */}
              {isLoading &&
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={`skel-${i}`} className="border-b border-neutral-100 animate-pulse">
                    <td className="px-4 h-11"><div className="h-3 w-16 bg-neutral-100 rounded" /></td>
                    <td className="px-4 h-11"><div className="h-3 w-48 bg-neutral-100 rounded" /></td>
                    <td className="px-4 h-11"><div className="h-3 w-20 bg-neutral-100 rounded" /></td>
                    <td className="px-4 h-11"><div className="h-5 w-14 bg-neutral-100 rounded-full" /></td>
                    <td className="px-4 h-11"><div className="h-3 w-12 bg-neutral-100 rounded" /></td>
                    <td className="px-4 h-11"><div className="h-3 w-16 bg-neutral-100 rounded" /></td>
                  </tr>
                ))}

              {/* 빈 상태 */}
              {!isLoading && cases.length === 0 && (
                <tr>
                  <td colSpan={6} className="h-48 text-center text-xs text-neutral-400">
                    검색 결과가 없습니다.
                  </td>
                </tr>
              )}

              {/* 데이터 행 */}
              {!isLoading &&
                cases.map((c) => <CaseRow key={c.id} caseItem={c} />)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

/* ── 테이블 행 컴포넌트 (각 케이스 1행) ── */
function CaseRow({ caseItem }: { caseItem: Case }) {
  const badge = STATUS_BADGE[caseItem.status];
  const priorityClass = PRIORITY_COLOR[caseItem.priority] ?? 'text-neutral-500';

  /* Case ID를 짧게 표시 (UUID 앞 8자리) */
  const shortId = caseItem.id.length > 8 ? caseItem.id.slice(0, 8) : caseItem.id;

  return (
    <tr className="border-b border-neutral-100 hover:bg-neutral-50/50 transition-colors">
      {/* Case ID — 파란색 링크, JetBrains Mono */}
      <td className="px-4 h-11">
        <Link
          to={ROUTES.CASES.DETAIL(caseItem.id)}
          className="text-xs font-mono text-blue-600 hover:text-blue-700 hover:underline"
        >
          {shortId}
        </Link>
      </td>

      {/* Title */}
      <td className="px-4 h-11 text-xs text-neutral-800 truncate max-w-0">
        <Link
          to={ROUTES.CASES.DETAIL(caseItem.id)}
          className="hover:text-blue-600 transition-colors"
        >
          {caseItem.title}
        </Link>
      </td>

      {/* Assignee */}
      <td className="px-4 h-11 text-xs text-neutral-400 truncate">
        {caseItem.assignee || '-'}
      </td>

      {/* Status — 색상 뱃지 */}
      <td className="px-4 h-11">
        {badge ? (
          <span
            className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full border ${badge.bg} ${badge.text} ${badge.border}`}
          >
            {badge.label}
          </span>
        ) : (
          <span className="text-xs text-neutral-400">{caseItem.status}</span>
        )}
      </td>

      {/* Priority — 컬러 텍스트 */}
      <td className="px-4 h-11">
        <span className={`text-xs ${priorityClass}`}>{caseItem.priority}</span>
      </td>

      {/* Updated — 상대 시간 */}
      <td className="px-4 h-11 text-xs text-neutral-400 tabular-nums">
        {relativeTime(caseItem.updatedAt ?? caseItem.createdAt)}
      </td>
    </tr>
  );
}
