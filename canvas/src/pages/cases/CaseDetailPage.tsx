/**
 * 케이스 상세 페이지 — axiom.pen 디자인 시스템 정렬.
 *
 * 레이아웃: 수평 분할 (좌: 케이스 정보 + 문서, 우: Activity Panel 300px)
 * 좌측: Case Info 카드 (2열 그리드) + Documents 카드 (파일 목록 + 업로드)
 * 우측: Activity Log (dot + title + timestamp 리스트)
 */
import { Link } from 'react-router-dom';
import { ArrowLeft, Upload, FileText, Clock } from 'lucide-react';
import { ROUTES } from '@/lib/routes/routes';
import { useCaseParams } from '@/lib/routes/params';
import { useCaseDetail } from '@/features/case-dashboard/hooks/useCaseDetail';
import { useCaseActivities } from '@/features/case-dashboard/hooks/useCaseActivities';
import { useDocumentList } from '@/features/document-management/hooks/useDocuments';

/* ── 상태 뱃지 색상 ── */
const STATUS_BADGE: Record<string, { label: string; bg: string; text: string; border: string }> = {
  PENDING: { label: '대기', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  IN_PROGRESS: { label: '진행 중', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  COMPLETED: { label: '완료', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  REJECTED: { label: '반려', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

/* ── 우선순위 색상 ── */
const PRIORITY_COLOR: Record<string, string> = {
  CRITICAL: 'text-red-600 font-semibold',
  HIGH: 'text-red-500',
  MEDIUM: 'text-orange-500',
  LOW: 'text-neutral-400',
};

/* ── 날짜 포맷 유틸 ── */
function formatDate(dateStr?: string): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

function formatTimestamp(dateStr: string): string {
  const d = new Date(dateStr);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return '방금';
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}일 전`;
  return d.toLocaleDateString('ko-KR');
}

/* ── 파일 크기 포맷 ── */
function formatFileSize(bytes?: number): string {
  if (!bytes) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const CaseDetailPage: React.FC = () => {
  const { caseId } = useCaseParams();

  /* ── 데이터 페칭 ── */
  const { data: caseItem, isLoading, error } = useCaseDetail(caseId);
  const { data: activities = [], isLoading: activitiesLoading } = useCaseActivities({
    caseId,
    limit: 30,
  });
  const { data: docsData, isLoading: docsLoading } = useDocumentList(caseId);
  const documents = docsData?.items ?? [];

  /* ── 로딩 상태 ── */
  if (isLoading) {
    return (
      <div className="flex h-full">
        <div className="flex-1 p-6 px-8 space-y-6">
          <div className="h-5 w-32 animate-pulse rounded bg-neutral-100" />
          <div className="bg-white rounded-xl border border-neutral-200 p-5 space-y-4">
            <div className="h-4 w-40 animate-pulse rounded bg-neutral-100" />
            <div className="grid grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-1.5">
                  <div className="h-3 w-16 animate-pulse rounded bg-neutral-100" />
                  <div className="h-4 w-28 animate-pulse rounded bg-neutral-100" />
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="w-[300px] border-l border-neutral-200 p-5">
          <div className="h-4 w-24 animate-pulse rounded bg-neutral-100" />
        </div>
      </div>
    );
  }

  /* ── 에러/미발견 상태 ── */
  if (error || !caseItem) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
        <p className="text-sm text-neutral-500">
          케이스를 찾을 수 없습니다. (ID: {caseId})
        </p>
        <Link
          to={ROUTES.CASES.LIST}
          className="text-xs text-blue-600 hover:underline flex items-center gap-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          목록으로 돌아가기
        </Link>
      </div>
    );
  }

  const badge = STATUS_BADGE[caseItem.status];
  const priorityClass = PRIORITY_COLOR[caseItem.priority] ?? 'text-neutral-500';

  return (
    <div className="flex h-full">
      {/* ══════════════ 좌측: 케이스 정보 + 문서 ══════════════ */}
      <div className="flex-1 min-w-0 flex flex-col gap-6 p-6 px-8 overflow-auto">
        {/* 뒤로가기 + 제목 */}
        <div className="flex items-center gap-3">
          <Link
            to={ROUTES.CASES.LIST}
            className="flex items-center justify-center h-8 w-8 rounded-lg border border-neutral-200 hover:bg-neutral-50 transition-colors"
            aria-label="목록으로 돌아가기"
          >
            <ArrowLeft className="h-4 w-4 text-neutral-500" />
          </Link>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-semibold text-neutral-900">{caseItem.title}</h1>
            {badge && (
              <span
                className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full border ${badge.bg} ${badge.text} ${badge.border}`}
              >
                {badge.label}
              </span>
            )}
          </div>
        </div>

        {/* ── Case Information 카드 ── */}
        <div className="bg-white border border-neutral-200 rounded-xl p-5 space-y-3">
          <h2 className="text-[13px] font-semibold text-neutral-900">Case Information</h2>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-4">
            {/* Assignee */}
            <InfoField label="Assignee" value={caseItem.assignee || '미배정'} />
            {/* Created */}
            <InfoField label="Created" value={formatDate(caseItem.createdAt)} />
            {/* Priority */}
            <div>
              <dt className="text-[11px] text-neutral-400 mb-0.5">Priority</dt>
              <dd className={`text-xs ${priorityClass}`}>{caseItem.priority}</dd>
            </div>
            {/* Last Updated */}
            <InfoField
              label="Last Updated"
              value={formatDate(caseItem.updatedAt ?? caseItem.createdAt)}
            />
          </dl>
        </div>

        {/* ── Documents 카드 ── */}
        <div className="bg-white border border-neutral-200 rounded-xl flex-1 min-h-0 flex flex-col">
          {/* 헤더 */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-neutral-100">
            <h2 className="text-[13px] font-semibold text-neutral-900">Documents</h2>
            <Link
              to={ROUTES.CASES.DOCUMENTS(caseId)}
              className="inline-flex items-center gap-1.5 h-7 px-3 text-[11px] font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
            >
              <Upload className="h-3 w-3" />
              Upload
            </Link>
          </div>

          {/* 문서 목록 */}
          <div className="flex-1 overflow-auto">
            {docsLoading ? (
              <div className="p-5 space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 animate-pulse">
                    <div className="h-8 w-8 rounded bg-neutral-100" />
                    <div className="space-y-1.5 flex-1">
                      <div className="h-3 w-40 rounded bg-neutral-100" />
                      <div className="h-2.5 w-16 rounded bg-neutral-100" />
                    </div>
                  </div>
                ))}
              </div>
            ) : documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-center">
                <FileText className="h-8 w-8 text-neutral-200 mb-2" />
                <p className="text-xs text-neutral-400">문서가 없습니다</p>
              </div>
            ) : (
              <ul className="divide-y divide-neutral-100">
                {documents.map((doc) => (
                  <li key={doc.id}>
                    <Link
                      to={ROUTES.CASES.DOCUMENT(caseId, doc.id)}
                      className="flex items-center gap-3 px-5 py-3 hover:bg-neutral-50 transition-colors"
                    >
                      <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-blue-50">
                        <FileText className="h-4 w-4 text-blue-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-neutral-800 truncate">
                          {doc.name}
                        </p>
                        <p className="text-[10px] text-neutral-400">
                          {doc.type?.toUpperCase() ?? 'FILE'}
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* ══════════════ 우측: Activity Panel (300px) ══════════════ */}
      <aside className="w-[300px] shrink-0 border-l border-neutral-200 flex flex-col bg-white">
        <div className="px-5 py-4 border-b border-neutral-100">
          <h2 className="text-[13px] font-semibold text-neutral-900">Activity Log</h2>
        </div>

        <div className="flex-1 overflow-auto px-5 py-4">
          {activitiesLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex gap-3 animate-pulse">
                  <div className="h-2 w-2 mt-1.5 rounded-full bg-neutral-100 shrink-0" />
                  <div className="space-y-1.5 flex-1">
                    <div className="h-3 w-full rounded bg-neutral-100" />
                    <div className="h-2.5 w-16 rounded bg-neutral-100" />
                  </div>
                </div>
              ))}
            </div>
          ) : activities.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-center">
              <Clock className="h-6 w-6 text-neutral-200 mb-2" />
              <p className="text-xs text-neutral-400">활동 내역이 없습니다</p>
            </div>
          ) : (
            <ul className="space-y-4">
              {activities.map((item) => (
                <li key={item.id} className="flex gap-3">
                  {/* 타임라인 dot */}
                  <div className="h-2 w-2 mt-1.5 rounded-full bg-blue-500 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-neutral-700 leading-snug">{item.text}</p>
                    <p className="text-[10px] text-neutral-400 mt-0.5">
                      {formatTimestamp(item.time)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
};

/* ── 2열 그리드용 정보 필드 (dl 내부에서 사용) ── */
function InfoField({ label, value }: { label: string; value: string }) {
  return (
    <div role="group">
      <dt className="text-[11px] text-neutral-400 mb-0.5">{label}</dt>
      <dd className="text-xs text-neutral-800">{value}</dd>
    </div>
  );
}
