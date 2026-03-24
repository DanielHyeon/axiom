/**
 * 릴리스 히스토리 타임라인 -- 시멘틱 스냅샷 이력을 시각적으로 표시.
 *
 * 각 릴리스를 타임라인 노드로 표현하고,
 * 활성/무효화/빌드중 상태를 색상으로 구분한다.
 * 변경 사항 요약 (added/changed/deleted)을 노드에 표시한다.
 */
import { useTranslation } from 'react-i18next';
import { Clock, GitCommit, History, Plus, Pencil, Trash2 } from 'lucide-react';

// ── 타입 정의 ──

/** 릴리스 노드 1건의 데이터 */
export interface ReleaseNode {
  /** 스냅샷 버전 (예: "v1.3.0") */
  version: string;
  /** 빌드 상태 */
  status: 'BUILDING' | 'READY' | 'ACTIVE' | 'INVALIDATED';
  /** 빌드 완료 시각 (ISO-8601) */
  builtAt: string;
  /** 변경 요약 (추가/변경/삭제 건수) */
  changes?: { added: number; changed: number; deleted: number };
}

export interface ReleaseTimelineProps {
  /** 릴리스 목록 (최신순) */
  releases: ReleaseNode[];
  /** 노드 클릭 시 콜백 */
  onSelect?: (version: string) => void;
  /** 현재 선택된 버전 */
  selectedVersion?: string;
}

// ── 상태별 색상 매핑 ──

const STATUS_CONFIG: Record<
  ReleaseNode['status'],
  { dot: string; ring: string; bg: string; text: string; label: string }
> = {
  ACTIVE: {
    dot: 'bg-green-500',
    ring: 'ring-green-200',
    bg: 'bg-green-50',
    text: 'text-green-700',
    label: 'Active',
  },
  READY: {
    dot: 'bg-blue-500',
    ring: 'ring-blue-200',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    label: 'Ready',
  },
  BUILDING: {
    dot: 'bg-yellow-500',
    ring: 'ring-yellow-200',
    bg: 'bg-yellow-50',
    text: 'text-yellow-700',
    label: 'Building',
  },
  INVALIDATED: {
    dot: 'bg-gray-400',
    ring: 'ring-gray-200',
    bg: 'bg-gray-50',
    text: 'text-gray-500',
    label: 'Invalidated',
  },
};

// ── 날짜 포맷 헬퍼 ──

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

// ── 변경 배지 컴포넌트 ──

/** 추가/변경/삭제 수를 배지로 표시 */
function ChangeBadges({ changes }: { changes: ReleaseNode['changes'] }) {
  if (!changes) return null;

  const { added, changed, deleted } = changes;
  // 모든 값이 0이면 아무것도 표시하지 않는다
  if (added === 0 && changed === 0 && deleted === 0) return null;

  return (
    <div className="flex items-center gap-1.5 mt-1.5">
      {added > 0 && (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700">
          <Plus className="h-3 w-3" />
          {added}
        </span>
      )}
      {changed > 0 && (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700">
          <Pencil className="h-3 w-3" />
          {changed}
        </span>
      )}
      {deleted > 0 && (
        <span className="inline-flex items-center gap-0.5 rounded-full bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700">
          <Trash2 className="h-3 w-3" />
          {deleted}
        </span>
      )}
    </div>
  );
}

// ── 타임라인 노드 컴포넌트 ──

interface TimelineNodeProps {
  release: ReleaseNode;
  isSelected: boolean;
  isLast: boolean;
  onSelect?: (version: string) => void;
}

function TimelineNode({ release, isSelected, isLast, onSelect }: TimelineNodeProps) {
  const { t } = useTranslation();
  const config = STATUS_CONFIG[release.status];

  return (
    <div className="relative flex gap-4">
      {/* 수직선 + 노드 점 */}
      <div className="flex flex-col items-center">
        {/* 상태 점 (클릭 가능) */}
        <button
          type="button"
          onClick={() => onSelect?.(release.version)}
          className={`
            relative z-10 flex h-4 w-4 shrink-0 items-center justify-center
            rounded-full ring-4
            ${config.dot} ${config.ring}
            ${isSelected ? 'scale-125 ring-offset-2' : ''}
            transition-transform duration-150
            cursor-pointer hover:scale-110
          `}
          aria-label={`${t('semanticCatalogExt.releaseTimeline.selectVersion')} ${release.version}`}
        >
          {/* BUILDING 상태면 펄스 애니메이션 */}
          {release.status === 'BUILDING' && (
            <span className="absolute inset-0 animate-ping rounded-full bg-yellow-400 opacity-40" />
          )}
        </button>

        {/* 수직 연결선 (마지막 노드가 아니면 표시) */}
        {!isLast && (
          <div className="w-0.5 grow bg-gray-200" />
        )}
      </div>

      {/* 카드 내용 */}
      <div
        className={`
          mb-4 w-full rounded-lg border p-3 transition-colors duration-150
          ${isSelected ? 'border-blue-300 bg-blue-50/50 shadow-sm' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/50'}
          cursor-pointer
        `}
        onClick={() => onSelect?.(release.version)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelect?.(release.version);
          }
        }}
        role="button"
        tabIndex={0}
        aria-selected={isSelected}
      >
        {/* 상단: 버전 + 상태 배지 */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <GitCommit className="h-4 w-4 text-gray-400" />
            <span className="font-mono text-sm font-semibold">{release.version}</span>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${config.bg} ${config.text}`}
          >
            {config.label}
          </span>
        </div>

        {/* 날짜 */}
        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-gray-500">
          <Clock className="h-3 w-3" />
          <time dateTime={release.builtAt}>{formatDate(release.builtAt)}</time>
        </div>

        {/* 변경 요약 배지 */}
        <ChangeBadges changes={release.changes} />
      </div>
    </div>
  );
}

// ── 메인 타임라인 컴포넌트 ──

export function ReleaseTimeline({ releases, onSelect, selectedVersion }: ReleaseTimelineProps) {
  const { t } = useTranslation();

  // 릴리스가 없으면 빈 상태 표시
  if (!releases || releases.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-gray-400">
        <History className="mb-3 h-8 w-8 opacity-50" />
        <p className="text-sm">{t('semanticCatalogExt.releaseTimeline.empty')}</p>
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* 헤더 */}
      <div className="mb-4 flex items-center gap-2">
        <History className="h-5 w-5 text-gray-500" />
        <h3 className="text-sm font-semibold text-gray-700">
          {t('semanticCatalogExt.releaseTimeline.title')}
        </h3>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
          {releases.length}{t('semanticCatalogExt.runtime.count')}
        </span>
      </div>

      {/* 타임라인 목록 */}
      <div className="pl-1">
        {releases.map((release, index) => (
          <TimelineNode
            key={release.version}
            release={release}
            isSelected={selectedVersion === release.version}
            isLast={index === releases.length - 1}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}
