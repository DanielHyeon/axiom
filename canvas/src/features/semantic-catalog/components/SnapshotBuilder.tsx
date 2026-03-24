/**
 * SnapshotBuilder -- 시맨틱 스냅샷 빌드 트리거 UI.
 *
 * RuntimePanel 내에서 사용되며, 새 스냅샷을 빌드/활성화/무효화한다.
 * Synapse API: POST /api/v3/synapse/semantic/snapshots/build
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Hammer,
  Loader2,
  Play,
  Ban,
  Camera,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  useActiveSnapshot,
  useBuildSnapshot,
  useActivateSnapshot,
  useInvalidateSnapshot,
  useSnapshots,
} from '../hooks/useSemanticCatalog';
import type { SemanticSnapshot } from '../types/semantic';

// ── 타입 정의 ──

export interface SnapshotBuilderProps {
  /** 현재 스냅샷 버전 (외부에서 전달, 없으면 내부 조회) */
  currentVersion?: string;
  /** 빌드 완료 후 콜백 */
  onBuildComplete?: () => void;
}

// ── 스냅샷 상태별 스타일 ──
const STATUS_STYLE: Record<string, { bg: string; text: string; icon: typeof CheckCircle2 }> = {
  BUILDING: { bg: 'bg-yellow-100', text: 'text-yellow-800', icon: Loader2 },
  READY: { bg: 'bg-blue-100', text: 'text-blue-800', icon: CheckCircle2 },
  ACTIVE: { bg: 'bg-green-100', text: 'text-green-800', icon: CheckCircle2 },
  INVALIDATED: { bg: 'bg-red-100', text: 'text-red-800', icon: AlertTriangle },
};

/** 날짜 포맷 헬퍼 */
function formatDate(dateStr?: string): string {
  if (!dateStr) return '--';
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

export function SnapshotBuilder({ currentVersion, onBuildComplete }: SnapshotBuilderProps) {
  const { t } = useTranslation();

  // 스냅샷 데이터 조회
  const { data: activeSnapshot, isLoading: activeLoading } = useActiveSnapshot();
  const { data: snapshots = [], isLoading: listLoading } = useSnapshots({ limit: 5 });

  // 뮤테이션 훅
  const buildSnapshot = useBuildSnapshot();
  const activateSnapshot = useActivateSnapshot();
  const invalidateSnap = useInvalidateSnapshot();

  // 무효화 사유 입력 상태
  const [invalidateTarget, setInvalidateTarget] = useState<string | null>(null);
  const [invalidateReason, setInvalidateReason] = useState('');

  // 표시할 현재 버전 (props 우선, 없으면 API 조회 결과)
  const displayVersion = currentVersion ?? activeSnapshot?.snapshot_version;

  // 빌드 핸들러
  const handleBuild = () => {
    buildSnapshot.mutate(
      {},
      {
        onSuccess: () => {
          onBuildComplete?.();
        },
      },
    );
  };

  // 활성화 핸들러
  const handleActivate = (version: string) => {
    activateSnapshot.mutate(version);
  };

  // 무효화 핸들러
  const handleInvalidate = (version: string) => {
    if (!invalidateReason.trim()) return;
    invalidateSnap.mutate(
      { version, reason: invalidateReason },
      {
        onSuccess: () => {
          setInvalidateTarget(null);
          setInvalidateReason('');
        },
      },
    );
  };

  const isLoading = activeLoading || listLoading;

  return (
    <div className="space-y-4" data-testid="snapshot-builder">
      {/* ── 현재 스냅샷 버전 표시 ── */}
      <div className="rounded-lg border bg-gradient-to-r from-blue-50 to-indigo-50 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Camera className="h-5 w-5 text-blue-600" />
          <h3 className="font-semibold text-blue-900">
            {t('snapshotBuilder.currentSnapshot')}
          </h3>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t('common.loading')}
          </div>
        ) : displayVersion ? (
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="font-mono text-sm">
              {displayVersion}
            </Badge>
            {activeSnapshot?.status && (
              <SnapshotStatusChip status={activeSnapshot.status} />
            )}
            {activeSnapshot?.activated_at && (
              <span className="text-xs text-muted-foreground font-mono">
                {formatDate(activeSnapshot.activated_at)}
              </span>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t('snapshotBuilder.noActiveSnapshot')}
          </p>
        )}
      </div>

      {/* ── 액션 버튼 ── */}
      <div className="flex items-center gap-2">
        <Button
          variant="default"
          size="sm"
          onClick={handleBuild}
          disabled={buildSnapshot.isPending}
        >
          {buildSnapshot.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
          ) : (
            <Hammer className="h-3.5 w-3.5 mr-1.5" />
          )}
          {t('snapshotBuilder.buildNew')}
        </Button>

        {/* 빌드 에러 표시 */}
        {buildSnapshot.isError && (
          <span className="text-xs text-destructive">
            {t('snapshotBuilder.buildFailed')}
          </span>
        )}

        {/* 빌드 성공 표시 */}
        {buildSnapshot.isSuccess && (
          <span className="text-xs text-green-600 flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" />
            {t('snapshotBuilder.buildStarted')}
          </span>
        )}
      </div>

      {/* ── 최근 스냅샷 목록 ── */}
      {snapshots.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {t('snapshotBuilder.recentSnapshots')}
          </h4>

          <div className="space-y-1.5">
            {snapshots.map((snap: SemanticSnapshot) => (
              <div
                key={snap.id}
                className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted/30 transition-colors"
              >
                {/* 버전 */}
                <span className="font-mono text-xs font-medium min-w-[80px]">
                  {snap.snapshot_version}
                </span>

                {/* 상태 */}
                <SnapshotStatusChip status={snap.status} />

                {/* 날짜 */}
                <span className="text-xs text-muted-foreground font-mono flex-1">
                  {formatDate(snap.built_at)}
                </span>

                {/* 액션 버튼 */}
                <div className="flex items-center gap-1 shrink-0">
                  {/* READY 상태 -> 활성화 가능 */}
                  {snap.status === 'READY' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-green-600 hover:text-green-700 hover:bg-green-50"
                      onClick={() => handleActivate(snap.snapshot_version)}
                      disabled={activateSnapshot.isPending}
                      title={t('snapshotBuilder.activate')}
                    >
                      <Play className="h-3 w-3 mr-1" />
                      <span className="text-xs">{t('snapshotBuilder.activate')}</span>
                    </Button>
                  )}

                  {/* ACTIVE 상태 -> 무효화 가능 */}
                  {snap.status === 'ACTIVE' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-red-500 hover:text-red-600 hover:bg-red-50"
                      onClick={() => setInvalidateTarget(snap.snapshot_version)}
                      disabled={invalidateSnap.isPending}
                      title={t('snapshotBuilder.invalidate')}
                    >
                      <Ban className="h-3 w-3 mr-1" />
                      <span className="text-xs">{t('snapshotBuilder.invalidate')}</span>
                    </Button>
                  )}

                  {/* INVALIDATED 상태 -> 사유 표시 */}
                  {snap.status === 'INVALIDATED' && snap.invalidation_reason && (
                    <span
                      className="text-[10px] text-muted-foreground italic truncate max-w-[120px]"
                      title={snap.invalidation_reason}
                    >
                      {snap.invalidation_reason}
                    </span>
                  )}
                </div>

                {/* 무효화 사유 입력 (인라인) */}
                {invalidateTarget === snap.snapshot_version && (
                  <div className="flex items-center gap-1 ml-2">
                    <Input
                      placeholder={t('snapshotBuilder.invalidateReasonPlaceholder')}
                      className="h-7 text-xs w-48"
                      value={invalidateReason}
                      onChange={(e) => setInvalidateReason(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleInvalidate(snap.snapshot_version);
                        if (e.key === 'Escape') {
                          setInvalidateTarget(null);
                          setInvalidateReason('');
                        }
                      }}
                      autoFocus
                    />
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-7 text-xs px-2"
                      onClick={() => handleInvalidate(snap.snapshot_version)}
                      disabled={invalidateSnap.isPending || !invalidateReason.trim()}
                    >
                      {t('common.confirm')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs px-2"
                      onClick={() => {
                        setInvalidateTarget(null);
                        setInvalidateReason('');
                      }}
                    >
                      {t('common.cancel')}
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── 스냅샷 상태 칩 ──
function SnapshotStatusChip({ status }: { status: string }) {
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.BUILDING;
  const Icon = style.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
    >
      <Icon className={`h-3 w-3 ${status === 'BUILDING' ? 'animate-spin' : ''}`} />
      {status}
    </span>
  );
}
