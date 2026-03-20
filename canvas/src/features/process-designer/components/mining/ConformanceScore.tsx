// features/process-designer/components/mining/ConformanceScore.tsx
// 적합도 점수 표시 (설계 §5.1)

interface ConformanceScoreProps {
 fitnessScore: number | null;
 loading: boolean;
}

function scoreColor(score: number): string {
 if (score >= 80) return '#22c55e';
 if (score >= 60) return '#f97316';
 return '#ef4444';
}

export function ConformanceScore({ fitnessScore, loading }: ConformanceScoreProps) {
 if (loading) {
 return (
 <div className="text-center py-3">
 <div className="w-6 h-6 border-2 border-border border-t-blue-400 rounded-full animate-spin mx-auto" />
 <div className="text-xs text-foreground0 mt-2">분석 중...</div>
 </div>
 );
 }

 if (fitnessScore === null) {
 return (
 <div className="text-center py-3 text-foreground0 text-xs">
 마이닝 데이터가 없습니다
 </div>
 );
 }

 return (
 <div className="text-center py-2">
 <div
 className="text-3xl font-bold"
 style={{ color: scoreColor(fitnessScore) }}
 >
 {fitnessScore.toFixed(1)}%
 </div>
 <div className="text-xs text-muted-foreground mt-1">적합도 점수</div>
 </div>
 );
}
