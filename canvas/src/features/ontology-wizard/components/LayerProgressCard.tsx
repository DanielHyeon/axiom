/**
 * LayerProgressCard — 단일 레이어의 생성 진행 상태 카드
 * 레이어 이름, 진행 바, 노드/관계 수, 상태 배지를 표시
 * 레이어별 색상 코딩: KPI=파랑, Measure=초록, Driver=주황, Process=보라, Resource=회색
 */
import { Loader2, Check, Clock, AlertCircle } from 'lucide-react';
import type { LayerProgress } from '../types/wizard';
import { LAYER_LABELS, LAYER_COLORS } from '../types/wizard';

interface LayerProgressCardProps {
  progress: LayerProgress;
}

/** 상태 배지 렌더링 */
function StatusBadge({ status }: { status: LayerProgress['status'] }) {
  switch (status) {
    case 'pending':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground">
          <Clock size={12} />
          대기
        </span>
      );
    case 'in_progress':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
          <Loader2 size={12} className="animate-spin" />
          진행 중
        </span>
      );
    case 'complete':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
          <Check size={12} />
          완료
        </span>
      );
    case 'error':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
          <AlertCircle size={12} />
          오류
        </span>
      );
  }
}

export function LayerProgressCard({ progress }: LayerProgressCardProps) {
  const { layer, progress: pct, message, nodeCount, relationCount, status } = progress;

  // 레이어별 색상 가져오기 (없으면 기본 회색)
  const colors = LAYER_COLORS[layer] ?? LAYER_COLORS['resource'];
  const label = LAYER_LABELS[layer] ?? layer;

  return (
    <div
      className={`
        rounded-lg border p-4 transition-all duration-300
        ${colors.bg} ${colors.border}
        ${status === 'in_progress' ? 'shadow-md' : 'shadow-sm'}
      `}
    >
      {/* 헤더: 레이어 이름 + 상태 배지 */}
      <div className="flex items-center justify-between mb-3">
        <h4 className={`text-sm font-semibold ${colors.text}`}>
          {label}
        </h4>
        <StatusBadge status={status} />
      </div>

      {/* 진행 바 */}
      <div className="h-2 bg-card/60 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${colors.progress}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>

      {/* 진행률 + 메시지 */}
      <div className="flex items-center justify-between text-xs mb-1">
        <span className={colors.text}>{Math.round(pct)}%</span>
        {message && (
          <span className="text-muted-foreground truncate ml-2 max-w-[60%]">
            {message}
          </span>
        )}
      </div>

      {/* 노드/관계 수 (값이 있을 때만 표시) */}
      {(nodeCount > 0 || relationCount > 0) && (
        <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
          <span>노드: <strong className={colors.text}>{nodeCount}</strong></span>
          <span>관계: <strong className={colors.text}>{relationCount}</strong></span>
        </div>
      )}
    </div>
  );
}
