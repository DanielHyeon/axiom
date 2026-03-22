/**
 * Sprint 3/4: 시멘틱 런타임 상태 패널
 *
 * 활성 릴리스, 배포 이력, 스냅샷 관리, 소비자 바인딩을 한 화면에 보여준다.
 * 운영자가 Oracle이 어떤 시멘틱 기준으로 답변하고 있는지 확인할 수 있다.
 */
import { useState } from 'react';
import {
  Clock,
  GitBranch,
  Rocket,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Camera,
  Play,
  Ban,
  Hammer,
  Loader2,
  Users,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { SemanticRelease, SemanticSnapshot } from '../types/semantic';
import {
  useSnapshots,
  useActiveSnapshot,
  useBuildSnapshot,
  useActivateSnapshot,
  useInvalidateSnapshot,
} from '../hooks/useSemanticCatalog';

interface RuntimePanelProps {
  /** 배포 이력 목록 (최신순) */
  releases: SemanticRelease[];
  /** 데이터 로딩 중 여부 */
  isLoading: boolean;
}

/** 배포 상태별 색상 매핑 */
const STATUS_STYLE: Record<string, { bg: string; text: string; icon: typeof CheckCircle2 }> = {
  published: { bg: 'bg-green-50', text: 'text-green-700', icon: CheckCircle2 },
  deployed: { bg: 'bg-green-50', text: 'text-green-700', icon: CheckCircle2 },
  approved: { bg: 'bg-blue-50', text: 'text-blue-700', icon: CheckCircle2 },
  pending: { bg: 'bg-yellow-50', text: 'text-yellow-700', icon: Clock },
  rejected: { bg: 'bg-red-50', text: 'text-red-700', icon: XCircle },
  rolled_back: { bg: 'bg-orange-50', text: 'text-orange-700', icon: AlertTriangle },
};

/** 스냅샷 상태별 색상 매핑 */
const SNAPSHOT_STATUS_STYLE: Record<string, { bg: string; text: string }> = {
  BUILDING: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
  READY: { bg: 'bg-blue-100', text: 'text-blue-800' },
  ACTIVE: { bg: 'bg-green-100', text: 'text-green-800' },
  INVALIDATED: { bg: 'bg-red-100', text: 'text-red-800' },
};

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleString('ko-KR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

/** 스냅샷 상태 배지 */
function SnapshotStatusBadge({ status }: { status: string }) {
  const style = SNAPSHOT_STATUS_STYLE[status] ?? SNAPSHOT_STATUS_STYLE.BUILDING;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
    >
      {status}
    </span>
  );
}

/** 스냅샷 관리 섹션 (RuntimePanel 하위) */
function SnapshotSection() {
  const { data: snapshots = [], isLoading: snapshotsLoading } = useSnapshots();
  const { data: activeSnapshot } = useActiveSnapshot();
  const buildSnapshot = useBuildSnapshot();
  const activateSnapshot = useActivateSnapshot();
  const invalidateSnap = useInvalidateSnapshot();

  // 무효화 사유 입력용
  const [invalidateTarget, setInvalidateTarget] = useState<string | null>(null);
  const [invalidateReason, setInvalidateReason] = useState('');

  /** 무효화 실행 */
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

  return (
    <div className="space-y-4">
      {/* 활성 스냅샷 요약 */}
      {activeSnapshot && (
        <div className="rounded-lg border bg-gradient-to-r from-green-50 to-emerald-50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Camera className="h-5 w-5 text-green-600" />
            <h3 className="font-semibold text-green-900">현재 활성 스냅샷</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground block text-xs mb-1">스냅샷 버전</span>
              <Badge variant="outline" className="font-mono">
                {activeSnapshot.snapshot_version}
              </Badge>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs mb-1">릴리스 버전</span>
              <span className="font-mono text-xs">{activeSnapshot.release_version}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs mb-1">콘텐츠 해시</span>
              <span className="font-mono text-xs text-muted-foreground">
                {activeSnapshot.content_hash?.slice(0, 12)}...
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs mb-1">활성화 시각</span>
              <span className="font-mono text-xs">{formatDate(activeSnapshot.activated_at)}</span>
            </div>
          </div>
        </div>
      )}

      {/* 스냅샷 목록 헤더 + 빌드 버튼 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Camera className="h-5 w-5 text-muted-foreground" />
          <h3 className="font-semibold">스냅샷 목록</h3>
          <Badge variant="secondary" className="text-xs">{snapshots.length}건</Badge>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => buildSnapshot.mutate({})}
          disabled={buildSnapshot.isPending}
        >
          {buildSnapshot.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
          ) : (
            <Hammer className="h-3.5 w-3.5 mr-1" />
          )}
          새 스냅샷 빌드
        </Button>
      </div>

      {/* 스냅샷 테이블 */}
      {snapshotsLoading ? (
        <div className="flex items-center justify-center py-8 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          스냅샷을 불러오는 중...
        </div>
      ) : snapshots.length === 0 ? (
        <div className="py-8 text-center text-muted-foreground text-sm border rounded-lg">
          스냅샷이 없습니다. 새 스냅샷을 빌드해 주세요.
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left font-medium">스냅샷 버전</th>
                <th className="px-3 py-2 text-left font-medium">릴리스 버전</th>
                <th className="px-3 py-2 text-center font-medium">상태</th>
                <th className="px-3 py-2 text-left font-medium">빌드 시각</th>
                <th className="px-3 py-2 text-left font-medium">활성화 시각</th>
                <th className="px-3 py-2 text-center font-medium">액션</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((snap: SemanticSnapshot) => (
                <tr key={snap.id} className="border-b hover:bg-muted/30">
                  <td className="px-3 py-2 font-mono text-xs font-medium">
                    {snap.snapshot_version}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {snap.release_version}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <SnapshotStatusBadge status={snap.status} />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {formatDate(snap.built_at)}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {formatDate(snap.activated_at)}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <div className="flex items-center justify-center gap-1">
                      {/* READY 상태 → 활성화 가능 */}
                      {snap.status === 'READY' && (
                        <button
                          className="p-1 rounded hover:bg-green-50"
                          title="활성화"
                          onClick={() => activateSnapshot.mutate(snap.snapshot_version)}
                          disabled={activateSnapshot.isPending}
                        >
                          <Play className="h-3.5 w-3.5 text-green-600" />
                        </button>
                      )}
                      {/* ACTIVE 상태 → 무효화 가능 */}
                      {snap.status === 'ACTIVE' && (
                        <button
                          className="p-1 rounded hover:bg-red-50"
                          title="무효화"
                          onClick={() => setInvalidateTarget(snap.snapshot_version)}
                          disabled={invalidateSnap.isPending}
                        >
                          <Ban className="h-3.5 w-3.5 text-red-500" />
                        </button>
                      )}
                      {/* INVALIDATED 상태 → 무효화 사유 표시 */}
                      {snap.status === 'INVALIDATED' && snap.invalidation_reason && (
                        <span
                          className="text-xs text-muted-foreground italic truncate max-w-[120px]"
                          title={snap.invalidation_reason}
                        >
                          {snap.invalidation_reason}
                        </span>
                      )}
                    </div>
                    {/* 무효화 사유 입력 인라인 */}
                    {invalidateTarget === snap.snapshot_version && (
                      <div className="flex items-center gap-1 mt-2">
                        <Input
                          placeholder="무효화 사유"
                          className="h-7 text-xs"
                          value={invalidateReason}
                          onChange={(e) => setInvalidateReason(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleInvalidate(snap.snapshot_version);
                            if (e.key === 'Escape') {
                              setInvalidateTarget(null);
                              setInvalidateReason('');
                            }
                          }}
                        />
                        <Button
                          type="button"
                          variant="destructive"
                          size="sm"
                          className="h-7 text-xs px-2"
                          onClick={() => handleInvalidate(snap.snapshot_version)}
                          disabled={invalidateSnap.isPending || !invalidateReason.trim()}
                        >
                          확인
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs px-2"
                          onClick={() => {
                            setInvalidateTarget(null);
                            setInvalidateReason('');
                          }}
                        >
                          취소
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 소비자 바인딩 플레이스홀더 */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Users className="h-5 w-5 text-muted-foreground" />
          <h3 className="font-semibold">소비자 바인딩</h3>
        </div>
        <div className="rounded-lg border border-dashed p-6 text-center text-muted-foreground">
          <Users className="h-6 w-6 mx-auto mb-2 opacity-50" />
          <p className="text-sm">소비자 바인딩 현황</p>
          <p className="text-xs mt-1">
            스냅샷에 바인딩된 소비자 서비스 (Oracle 등) 목록이 여기에 표시됩니다
          </p>
        </div>
      </div>
    </div>
  );
}

export function RuntimePanel({ releases, isLoading }: RuntimePanelProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <Clock className="h-5 w-5 animate-spin mr-2" />
        릴리스 이력을 불러오는 중...
      </div>
    );
  }

  // 최신 릴리스 = 목록의 첫 번째 항목
  const latestRelease = releases[0] ?? null;

  return (
    <div className="space-y-6">
      {/* 현재 활성 릴리스 요약 카드 */}
      <div className="rounded-lg border bg-gradient-to-r from-blue-50 to-indigo-50 p-4">
        <div className="flex items-center gap-2 mb-3">
          <GitBranch className="h-5 w-5 text-blue-600" />
          <h3 className="font-semibold text-blue-900">현재 활성 시멘틱 릴리스</h3>
        </div>
        {latestRelease ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground block text-xs mb-1">릴리스 ID</span>
              <span className="font-mono font-medium">#{latestRelease.release_id}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs mb-1">대상</span>
              <span className="font-medium">{latestRelease.semantic_object_type}</span>
              <span className="text-muted-foreground ml-1 font-mono text-xs">
                {latestRelease.semantic_object_id}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs mb-1">버전</span>
              <Badge variant="outline" className="font-mono">v{latestRelease.version}</Badge>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs mb-1">배포 시각</span>
              <span className="font-mono text-xs">{formatDate(latestRelease.deployed_at)}</span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">배포된 릴리스가 없습니다</p>
        )}
      </div>

      {/* 배포 이력 타임라인 */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Rocket className="h-5 w-5 text-muted-foreground" />
          <h3 className="font-semibold">배포 이력 타임라인</h3>
          <Badge variant="secondary" className="text-xs">{releases.length}건</Badge>
        </div>

        {releases.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground text-sm border rounded-lg">
            배포 이력이 없습니다
          </div>
        ) : (
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium w-16">#</th>
                  <th className="px-3 py-2 text-left font-medium">대상 타입</th>
                  <th className="px-3 py-2 text-left font-medium">대상 ID</th>
                  <th className="px-3 py-2 text-center font-medium">버전</th>
                  <th className="px-3 py-2 text-center font-medium">상태</th>
                  <th className="px-3 py-2 text-left font-medium">검토자</th>
                  <th className="px-3 py-2 text-left font-medium">배포 시각</th>
                </tr>
              </thead>
              <tbody>
                {releases.map((rel) => {
                  const style = STATUS_STYLE[rel.review_status?.toLowerCase()] ?? STATUS_STYLE.pending;
                  const StatusIcon = style.icon;
                  return (
                    <tr key={rel.release_id} className="border-b hover:bg-muted/30">
                      <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                        {rel.release_id}
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant="outline" className="text-xs">
                          {rel.semantic_object_type}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">{rel.semantic_object_id}</td>
                      <td className="px-3 py-2 text-center">
                        <span className="font-mono text-xs">v{rel.version}</span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs ${style.bg} ${style.text}`}>
                          <StatusIcon className="h-3 w-3" />
                          {rel.review_status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {rel.reviewer || '—'}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                        {formatDate(rel.deployed_at || rel.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── 스냅샷 관리 섹션 ── */}
      <div className="border-t pt-6">
        <SnapshotSection />
      </div>
    </div>
  );
}
