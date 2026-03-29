/**
 * Watch / Alerts 페이지 — .pen 디자인 사양 기반 리라이트
 *
 * 레이아웃: 수평 분할
 *   좌측(fill): Alert Rules 카드 목록
 *   우측(360px): Recent Events 피드
 *
 * 백엔드 연동: GET /api/v1/watches/rules, /api/v1/watches/alerts (Core 서비스)
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bell,
  TriangleAlert,
  Gauge,
  Activity,
  Loader2,
  AlertCircle,
  BellOff,
} from 'lucide-react';
import { useWatchRules } from '@/features/watch/hooks/useWatchRules';
import { useAlerts } from '@/features/watch/hooks/useAlerts';
import type { WatchRule, Alert, AlertSeverity } from '@/features/watch/types/watch';

// ── 규칙 아이콘 매핑 — event_type 기반 색상 구분 ──
const RULE_ICON_CONFIG: Record<string, { icon: typeof Bell; bg: string; fg: string }> = {
  threshold: { icon: Gauge, bg: 'bg-amber-100', fg: 'text-amber-700' },
  anomaly: { icon: TriangleAlert, bg: 'bg-red-100', fg: 'text-red-700' },
  change: { icon: Activity, bg: 'bg-blue-100', fg: 'text-blue-700' },
};

function getRuleIcon(eventType: string) {
  return RULE_ICON_CONFIG[eventType] ?? { icon: Bell, bg: 'bg-amber-100', fg: 'text-amber-700' };
}

// ── 이벤트 심각도별 텍스트 색상 ──
const SEVERITY_COLORS: Record<AlertSeverity, string> = {
  critical: 'text-red-600',
  warning: 'text-orange-500',
  info: 'text-green-500',
};

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

export function WatchDashboardPage() {
  const { t } = useTranslation();
  const { rules, loading: rulesLoading, error: rulesError } = useWatchRules();
  const { alerts, isLoading: alertsLoading, loadError: alertsError, markAsRead } = useAlerts();

  // 현재 활성 규칙 ID (클릭 시 강조)
  const [activeRuleId, setActiveRuleId] = useState<string | null>(null);

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── 좌측: Alert Rules ── */}
      <div className="flex-1 flex flex-col gap-4 py-6 px-8 overflow-y-auto">
        <h2 className="font-heading text-base font-semibold text-foreground">
          Alert Rules
        </h2>

        {/* 로딩 상태 */}
        {rulesLoading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* 에러 상태 */}
        {rulesError && !rulesLoading && (
          <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{t('watch.loadError', '규칙을 불러올 수 없습니다.')}</span>
          </div>
        )}

        {/* 빈 상태 */}
        {!rulesLoading && !rulesError && rules.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
            <BellOff className="h-10 w-10" />
            <p className="text-sm">{t('watch.noRules', '등록된 알림 규칙이 없습니다.')}</p>
          </div>
        )}

        {/* 규칙 카드 목록 */}
        <div className="flex flex-col gap-3">
          {rules.map((rule) => (
            <RuleCard
              key={rule.rule_id}
              rule={rule}
              isActive={activeRuleId === rule.rule_id}
              onClick={() => setActiveRuleId(rule.rule_id)}
            />
          ))}
        </div>
      </div>

      {/* ── 우측: Event Feed (360px) ── */}
      <div className="w-[360px] shrink-0 flex flex-col gap-4 py-6 px-5 border-l border-border overflow-y-auto">
        <h3 className="font-heading text-[13px] font-semibold text-foreground">
          Recent Events
        </h3>

        {/* 로딩 상태 */}
        {alertsLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* 에러 상태 */}
        {alertsError && !alertsLoading && (
          <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>이벤트를 불러올 수 없습니다.</span>
          </div>
        )}

        {/* 빈 상태 */}
        {!alertsLoading && !alertsError && alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-muted-foreground">
            <Bell className="h-8 w-8" />
            <p className="text-xs">최근 이벤트가 없습니다.</p>
          </div>
        )}

        {/* 이벤트 카드 목록 */}
        <div className="flex flex-col gap-3">
          {alerts.slice(0, 50).map((alert) => (
            <EventCard key={alert.id} alert={alert} onRead={markAsRead} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Rule Card 컴포넌트 ──

interface RuleCardProps {
  rule: WatchRule;
  isActive: boolean;
  onClick: () => void;
}

function RuleCard({ rule, isActive, onClick }: RuleCardProps) {
  const iconConfig = getRuleIcon(rule.event_type);
  const Icon = iconConfig.icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'flex items-center gap-3 w-full rounded-lg bg-white p-4 text-left transition-all',
        isActive
          ? 'ring-2 ring-primary'
          : 'border border-border hover:border-primary/30',
      ].join(' ')}
    >
      {/* 아이콘 배경 (36x36) */}
      <div
        className={`flex items-center justify-center shrink-0 w-9 h-9 rounded-lg ${iconConfig.bg}`}
      >
        <Icon className={`h-4 w-4 ${iconConfig.fg}`} />
      </div>

      {/* 정보 영역 */}
      <div className="flex-1 min-w-0 flex flex-col gap-0.5">
        <span className="text-[13px] font-medium text-foreground truncate">
          {rule.name}
        </span>
        <span className="text-[11px] text-muted-foreground truncate">
          {rule.event_type}
        </span>
      </div>

      {/* 상태 배지 */}
      <span
        className={[
          'shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold',
          rule.active
            ? 'bg-green-100 text-green-800'
            : 'bg-slate-100 text-slate-500',
        ].join(' ')}
      >
        {rule.active ? 'Active' : 'Inactive'}
      </span>
    </button>
  );
}

// ── Event Card 컴포넌트 ──

interface EventCardProps {
  alert: Alert;
  onRead: (id: string) => void;
}

function EventCard({ alert, onRead }: EventCardProps) {
  const color = SEVERITY_COLORS[alert.severity] ?? 'text-foreground';

  return (
    <button
      type="button"
      onClick={() => !alert.isRead && onRead(alert.id)}
      className="flex flex-col gap-1 rounded-lg bg-white p-3 border border-border text-left hover:border-primary/30 transition-colors w-full"
    >
      <span className={`text-xs font-medium ${color} leading-snug`}>
        {alert.title}
      </span>
      <span className="text-[11px] text-muted-foreground leading-snug">
        {alert.description} · {relativeTime(alert.timestamp)}
      </span>
    </button>
  );
}
