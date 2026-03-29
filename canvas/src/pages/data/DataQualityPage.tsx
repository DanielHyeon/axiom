/**
 * DataQualityPage — .pen 디자인 사양 기반 리라이트
 *
 * 레이아웃: 수직, 24px 패딩, 48px 좌우, 20px 갭
 *   1) Score Cards 행: 5개 동일 카드 (Freshness, Completeness, Validity, Uniqueness, Ref Integrity)
 *   2) Trust Level 바: 흰색 카드, 수평 — 라벨 + "TRUSTED" 배지 + 점수
 *   3) Breaches 테이블: 흰색 카드, fill 높이, 헤더 + 행 (dot + 설명 + 시간)
 *
 * 색상 코딩: green >= 90, orange 70-89, red < 70
 *
 * 백엔드 연동: GET /api/quality/scores, /api/quality/breaches (Weaver 서비스)
 */
import { Loader2, AlertCircle, ShieldCheck } from 'lucide-react';
import { useDQScore, useDQIncidents } from '@/features/data-quality/hooks/useDQMetrics';
import type { DQScore, DQIncident } from '@/features/data-quality/types/data-quality';

// ── 점수 색상 유틸 — green >= 90, orange 70-89, red < 70 ──
function scoreColor(value: number): string {
  if (value >= 90) return 'text-green-500';
  if (value >= 70) return 'text-orange-500';
  return 'text-red-500';
}

// ── Trust 등급 계산 ──
function computeTrust(score: DQScore): { tier: string; value: number; color: string; badgeBg: string; badgeText: string } {
  // 5개 차원의 가중 평균 (Weaver 9차원 → Canvas 5차원 매핑 후)
  const avg = (score.completeness + score.accuracy + score.consistency + score.timeliness + score.overall) / 5;
  const rounded = Math.round(avg * 10) / 10;

  if (rounded >= 80) {
    return { tier: 'TRUSTED', value: rounded, color: 'text-green-500', badgeBg: 'bg-green-100', badgeText: 'text-green-800' };
  }
  if (rounded >= 60) {
    return { tier: 'CAUTION', value: rounded, color: 'text-orange-500', badgeBg: 'bg-orange-100', badgeText: 'text-orange-800' };
  }
  if (rounded >= 40) {
    return { tier: 'REFERENCE_ONLY', value: rounded, color: 'text-orange-600', badgeBg: 'bg-orange-100', badgeText: 'text-orange-700' };
  }
  return { tier: 'BLOCKED', value: rounded, color: 'text-red-500', badgeBg: 'bg-red-100', badgeText: 'text-red-800' };
}

// ── 상대 시간 포매터 ──
function relativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '방금 전';
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

// ── Breach 심각도별 dot 색상 ──
function breachDotColor(severity: DQIncident['severity']): string {
  if (severity === 'critical') return 'bg-red-500';
  if (severity === 'warning') return 'bg-orange-500';
  return 'bg-blue-500';
}

// ── Score Card 정의 ──
interface ScoreCardDef {
  label: string;
  key: keyof DQScore;
}

const SCORE_CARDS: ScoreCardDef[] = [
  { label: 'Freshness', key: 'timeliness' },
  { label: 'Completeness', key: 'completeness' },
  { label: 'Validity', key: 'accuracy' },
  { label: 'Uniqueness', key: 'consistency' },
  { label: 'Ref Integrity', key: 'overall' },
];

export function DataQualityPage() {
  const { data: score, isLoading: scoreLoading, error: scoreError } = useDQScore();
  const { data: incidents, isLoading: incidentsLoading, error: incidentsError } = useDQIncidents();

  // 전체 로딩
  if (scoreLoading && incidentsLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const dqScore = score ?? { overall: 0, completeness: 0, accuracy: 0, consistency: 0, timeliness: 0 };
  const trust = computeTrust(dqScore);
  const breaches = incidents ?? [];

  return (
    <div className="flex flex-col h-full gap-5 py-6 px-12 overflow-y-auto">
      {/* ── 1) Score Cards 행 ── */}
      <div className="flex gap-3">
        {SCORE_CARDS.map((card) => {
          const value = dqScore[card.key];
          return (
            <div
              key={card.key}
              className="flex-1 flex flex-col gap-1.5 rounded-xl bg-white border border-border p-4"
            >
              <span className="text-[11px] text-muted-foreground">{card.label}</span>
              <span className={`font-heading text-2xl font-bold ${scoreColor(value)}`}>
                {value}%
              </span>
            </div>
          );
        })}
      </div>

      {/* 에러 안내 (점수) */}
      {scoreError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>품질 점수를 불러올 수 없습니다. Mock 데이터로 표시합니다.</span>
        </div>
      )}

      {/* ── 2) Trust Level 바 ── */}
      <div className="flex items-center gap-6 rounded-xl bg-white border border-border p-5">
        <span className="font-heading text-sm font-semibold text-foreground">
          Overall Trust Level
        </span>
        <span
          className={`rounded-md px-4 py-1.5 font-mono text-xs font-bold ${trust.badgeBg} ${trust.badgeText}`}
        >
          {trust.tier}
        </span>
        <span className={`font-heading text-xl font-bold ${trust.color}`}>
          {trust.value} / 100
        </span>
      </div>

      {/* ── 3) Breaches 테이블 ── */}
      <div className="flex-1 flex flex-col rounded-xl bg-white border border-border overflow-hidden min-h-0">
        {/* 헤더 */}
        <div className="flex items-center h-11 px-4 border-b border-border shrink-0">
          <span className="font-heading text-[13px] font-semibold text-foreground">
            Recent Breaches
          </span>
        </div>

        {/* 로딩 */}
        {incidentsLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* 에러 */}
        {incidentsError && !incidentsLoading && (
          <div className="flex items-center gap-2 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>Breach 데이터를 불러올 수 없습니다.</span>
          </div>
        )}

        {/* 빈 상태 */}
        {!incidentsLoading && breaches.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
            <ShieldCheck className="h-10 w-10" />
            <p className="text-sm">위반 항목이 없습니다.</p>
          </div>
        )}

        {/* Breach 행 */}
        <div className="flex-1 overflow-y-auto">
          {breaches.map((breach) => (
            <div
              key={breach.id}
              className="flex items-center gap-2.5 h-10 px-4 border-b border-border last:border-b-0"
            >
              {/* 심각도 dot */}
              <div className={`w-2 h-2 rounded-full shrink-0 ${breachDotColor(breach.severity)}`} />

              {/* 설명 */}
              <span className="flex-1 text-xs text-foreground truncate">
                {breach.ruleName}
                {breach.tableName ? ` on ${breach.tableName}` : ''}
              </span>

              {/* 시간 */}
              <span className="shrink-0 text-[11px] text-muted-foreground">
                {relativeTime(breach.detectedAt)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
