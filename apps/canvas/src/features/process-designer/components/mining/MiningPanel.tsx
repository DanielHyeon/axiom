// features/process-designer/components/mining/MiningPanel.tsx
// 프로세스 마이닝 결과 사이드 패널 — ConformanceScore + VariantList + 컨트롤

import { ConformanceScore } from './ConformanceScore';
import { VariantList } from './VariantList';
import type { ConformanceResult, BottleneckResult } from '../../api/processDesignerApi';

interface MiningPanelProps {
 conformance: ConformanceResult | null;
 bottlenecks: BottleneckResult | null;
 loading: boolean;
 error: string | null;
 overlayVisible: boolean;
 onToggleOverlay: () => void;
 onRefresh: () => void;
 selectedVariant: number | null;
 onSelectVariant: (index: number | null) => void;
}

export function MiningPanel({
 conformance,
 bottlenecks,
 loading,
 error,
 overlayVisible,
 onToggleOverlay,
 onRefresh,
 selectedVariant,
 onSelectVariant,
}: MiningPanelProps) {
 return (
 <div className="border-t border-border mt-auto">
 {/* Header */}
 <div className="flex items-center justify-between px-3 py-2 border-b border-border">
 <span className="text-xs font-semibold text-foreground/80">프로세스 마이닝</span>
 <div className="flex items-center gap-1.5">
 <button
 type="button"
 onClick={onToggleOverlay}
 className={`text-xs px-2 py-0.5 rounded ${
 overlayVisible
 ? 'bg-primary text-white'
 : 'bg-muted text-muted-foreground hover:text-foreground'
 }`}
 >
 {overlayVisible ? '오버레이 ON' : '오버레이 OFF'}
 </button>
 <button
 type="button"
 onClick={onRefresh}
 disabled={loading}
 className="text-xs text-foreground0 hover:text-foreground/80 disabled:opacity-50"
 >
 새로고침
 </button>
 </div>
 </div>

 {/* Error */}
 {error && (
 <div className="px-3 py-2 text-xs text-destructive bg-red-900/20">
 {error}
 </div>
 )}

 {/* Score */}
 <ConformanceScore
 fitnessScore={conformance?.fitnessScore ?? null}
 loading={loading}
 />

 {/* Bottleneck summary */}
 {bottlenecks && bottlenecks.bottlenecks.length > 0 && (
 <div className="px-3 py-2 border-t border-border">
 <div className="text-xs text-muted-foreground mb-1">병목 지점</div>
 {bottlenecks.bottlenecks.map((bn) => (
 <div
 key={bn.activityName}
 className="flex items-center justify-between text-xs py-0.5"
 >
 <span className="text-foreground/80 truncate">{bn.activityName}</span>
 <span
 className={
 bn.severity === 'high'
 ? 'text-destructive'
 : bn.severity === 'medium'
 ? 'text-orange-400'
 : 'text-success'
 }
 >
 {bn.avgWaitTime.toFixed(0)}분
 </span>
 </div>
 ))}
 </div>
 )}

 {/* Variant list */}
 <div className="border-t border-border max-h-48 overflow-auto">
 <VariantList
 conformance={conformance}
 selectedVariant={selectedVariant}
 onSelectVariant={onSelectVariant}
 loading={loading}
 />
 </div>
 </div>
 );
}
