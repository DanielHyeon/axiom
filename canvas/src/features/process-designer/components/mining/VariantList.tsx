// features/process-designer/components/mining/VariantList.tsx
// 변형 목록 — 클릭 시 캔버스에 해당 경로 하이라이트 (설계 §5.1)

import type { ConformanceResult } from '../../api/processDesignerApi';

interface VariantListProps {
 conformance: ConformanceResult | null;
 selectedVariant: number | null;
 onSelectVariant: (index: number | null) => void;
 loading: boolean;
}

export function VariantList({
 conformance,
 selectedVariant,
 onSelectVariant,
 loading,
}: VariantListProps) {
 if (loading) {
 return (
 <div className="p-3 space-y-2">
 {Array.from({ length: 3 }).map((_, i) => (
 <div key={i} className="h-8 rounded bg-muted animate-pulse" />
 ))}
 </div>
 );
 }

 if (!conformance || conformance.deviations.length === 0) {
 return (
 <div className="p-3 text-xs text-foreground0 text-center">
 변형 데이터가 없습니다. 이벤트 로그를 바인딩하세요.
 </div>
 );
 }

 // 빈도 내림차순 정렬
 const sorted = [...conformance.deviations].sort((a, b) => b.frequency - a.frequency);
 const maxFreq = sorted[0]?.frequency ?? 1;

 return (
 <div className="space-y-1 p-2">
 <div className="text-xs text-muted-foreground px-1 mb-2">
 변형 목록 ({sorted.length}개)
 </div>
 {sorted.map((dev, i) => {
 const isDeviation = dev.percentage > 0;
 const barColor = isDeviation ? '#ef4444' : '#22c55e';
 const isSelected = selectedVariant === i;

 return (
 <button
 key={i}
 type="button"
 onClick={() => onSelectVariant(isSelected ? null : i)}
 className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
 isSelected
 ? 'bg-blue-900/50 border border-blue-600'
 : 'hover:bg-muted border border-transparent'
 }`}
 >
 <div className="flex items-center justify-between mb-1">
 <span className="text-foreground/80 truncate flex-1">
 {dev.path.join(' → ')}
 </span>
 <span className="text-foreground0 ml-2 shrink-0">
 {dev.frequency}건
 </span>
 </div>
 {/* 빈도 바 */}
 <div className="h-1.5 bg-muted rounded-full overflow-hidden">
 <div
 className="h-full rounded-full transition-all"
 style={{
 width: `${(dev.frequency / maxFreq) * 100}%`,
 backgroundColor: barColor,
 }}
 />
 </div>
 </button>
 );
 })}
 </div>
 );
}
