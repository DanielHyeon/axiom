/**
 * DQScoreCard — DQ 점수 카드 (도넛 게이지 포함)
 * KAIR DataQuality.vue의 stats-cards 섹션을 React+Tailwind로 이식
 */
import { useDQStats } from '../hooks/useDQMetrics';

// SVG 도넛 게이지 컴포넌트
function DonutGauge({
  value,
  color = 'text-green-500',
  bgColor = 'stroke-muted',
}: {
  value: number;
  color?: string;
  bgColor?: string;
}) {
  return (
    <div className="relative w-20 h-20">
      <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
        {/* 배경 원 */}
        <path
          className={bgColor}
          fill="none"
          strokeWidth="3"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
        {/* 값 원 */}
        <path
          className={color}
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={`${value}, 100`}
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
      </svg>
      {/* 중앙 텍스트 */}
      <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold text-foreground">
        {value}%
      </span>
    </div>
  );
}

export function DQScoreCard() {
  const stats = useDQStats();

  if (!stats) {
    return (
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* 카드 1: 전체 테스트 */}
      <div className="flex items-center justify-between p-5 bg-card border border-border rounded-lg">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">전체 테스트</p>
          <p className="text-3xl font-bold text-foreground">{stats.totalTests}</p>
        </div>
        <div className="flex items-center gap-3">
          <DonutGauge value={stats.successRate} color="text-green-500" />
          <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              성공 {stats.successCount}
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-yellow-500" />
              중단 {stats.abortedCount}
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              실패 {stats.failedCount}
            </span>
          </div>
        </div>
      </div>

      {/* 카드 2: 정상 데이터 자산 */}
      <div className="flex items-center justify-between p-5 bg-card border border-border rounded-lg">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">정상 데이터 자산</p>
          <p className="text-3xl font-bold text-foreground">{stats.healthyAssets}</p>
        </div>
        <DonutGauge value={stats.healthyRate} color="text-primary" />
      </div>

      {/* 카드 3: 데이터 자산 커버리지 */}
      <div className="flex items-center justify-between p-5 bg-card border border-border rounded-lg">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">데이터 자산 커버리지</p>
          <p className="text-3xl font-bold text-foreground">{stats.totalAssets}</p>
        </div>
        <DonutGauge value={Math.round(stats.coverageRate)} color="text-primary" />
      </div>
    </div>
  );
}
