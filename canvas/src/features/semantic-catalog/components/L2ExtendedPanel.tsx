/**
 * L2 확장 패널 — 세그먼트 | 시간 계약 | 접근 정책 (3개 서브탭)
 *
 * 시멘틱 엔티티에 연결된 세그먼트 정의, 시간 계약, 접근 정책을
 * 서브탭 형태로 전환하며 각각 읽기 전용 테이블로 표시한다.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Filter, Clock, Lock } from 'lucide-react';
import type { SemanticSegment, TimeContract, AccessPolicyL2 } from '../types/semantic';

type SubTab = 'segments' | 'time-contracts' | 'access-policies';

// ── 세그먼트 타입 배지 색상 ──
const SEGMENT_TYPE_COLORS: Record<string, string> = {
  static: 'bg-slate-100 text-slate-700',
  dynamic: 'bg-blue-50 text-blue-700',
  cohort: 'bg-violet-50 text-violet-700',
  computed: 'bg-emerald-50 text-emerald-700',
};

// ── 시간 단위 배지 색상 ──
const TIME_GRAIN_COLORS: Record<string, string> = {
  day: 'bg-blue-50 text-blue-700',
  week: 'bg-cyan-50 text-cyan-700',
  month: 'bg-emerald-50 text-emerald-700',
  quarter: 'bg-amber-50 text-amber-700',
  year: 'bg-violet-50 text-violet-700',
  hour: 'bg-slate-100 text-slate-700',
};

// ── 접근 정책 타입 배지 색상 ──
const ACCESS_POLICY_COLORS: Record<string, string> = {
  row_filter: 'bg-rose-50 text-rose-700',
  column_mask: 'bg-amber-50 text-amber-700',
  deny: 'bg-red-100 text-red-800',
  allow: 'bg-green-50 text-green-700',
};

const SUB_TABS: { key: SubTab; labelKey: string; icon: typeof Filter }[] = [
  { key: 'segments', labelKey: 'semanticCatalog.l2Extended.segments', icon: Filter },
  { key: 'time-contracts', labelKey: 'semanticCatalog.l2Extended.timeContracts', icon: Clock },
  { key: 'access-policies', labelKey: 'semanticCatalog.l2Extended.accessPolicies', icon: Lock },
];

interface Props {
  segments: SemanticSegment[];
  timeContracts: TimeContract[];
  accessPolicies: AccessPolicyL2[];
}

export function L2ExtendedPanel({ segments, timeContracts, accessPolicies }: Props) {
  const { t } = useTranslation();
  const [subTab, setSubTab] = useState<SubTab>('segments');

  return (
    <div className="rounded-lg border">
      {/* 서브탭 네비게이션 */}
      <div className="flex border-b bg-muted/30">
        {SUB_TABS.map(({ key, labelKey, icon: Icon }) => (
          <button
            key={key}
            className={`
              flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors
              ${subTab === key
                ? 'border-b-2 border-primary text-primary'
                : 'text-muted-foreground hover:text-foreground'
              }
            `}
            onClick={() => setSubTab(key)}
          >
            <Icon className="h-3.5 w-3.5" />
            {t(labelKey)}
            {/* 카운트 배지 */}
            <span className="ml-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] tabular-nums">
              {key === 'segments' ? segments.length : key === 'time-contracts' ? timeContracts.length : accessPolicies.length}
            </span>
          </button>
        ))}
      </div>

      {/* ═══════ 세그먼트 테이블 ═══════ */}
      {subTab === 'segments' && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.segmentId')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.entityId')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.name')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.filterExpression')}</th>
                <th className="px-3 py-2 text-center font-medium">{t('semanticCatalogExt.type')}</th>
              </tr>
            </thead>
            <tbody>
              {segments.map((s) => {
                const typeBadge = SEGMENT_TYPE_COLORS[s.segment_type] ?? SEGMENT_TYPE_COLORS.static;
                return (
                  <tr key={s.segment_id} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-2 font-mono text-xs">{s.segment_id}</td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{s.entity_id}</td>
                    <td className="px-3 py-2 font-medium">{s.name}</td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground max-w-[300px] truncate" title={s.filter_expression}>
                      {s.filter_expression}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${typeBadge}`}>
                        {s.segment_type}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {segments.length === 0 && (
            <div className="py-8 text-center text-muted-foreground text-sm">{t('semanticCatalog.l2Extended.noSegments')}</div>
          )}
        </>
      )}

      {/* ═══════ 시간 계약 테이블 ═══════ */}
      {subTab === 'time-contracts' && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.entityId')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.timeColumn')}</th>
                <th className="px-3 py-2 text-center font-medium">{t('semanticCatalogExt.timeGrain')}</th>
                <th className="px-3 py-2 text-center font-medium">{t('semanticCatalogExt.timezone')}</th>
                <th className="px-3 py-2 text-center font-medium">{t('semanticCatalogExt.fiscalOffset')}</th>
                <th className="px-3 py-2 text-center font-medium">{t('semanticCatalogExt.lookbackDays')}</th>
              </tr>
            </thead>
            <tbody>
              {timeContracts.map((tc) => {
                const grainBadge = TIME_GRAIN_COLORS[tc.time_grain] ?? TIME_GRAIN_COLORS.day;
                return (
                  <tr key={tc.time_contract_id} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{tc.entity_id}</td>
                    <td className="px-3 py-2 font-mono text-xs">{tc.time_column}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${grainBadge}`}>
                        {tc.time_grain}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center text-xs text-muted-foreground">{tc.timezone}</td>
                    <td className="px-3 py-2 text-center tabular-nums text-xs">
                      {tc.fiscal_calendar_offset === 0 ? '—' : `${tc.fiscal_calendar_offset}${t('semanticCatalogExt.months')}`}
                    </td>
                    <td className="px-3 py-2 text-center tabular-nums text-xs">
                      {tc.default_lookback_days}{t('semanticCatalogExt.days')}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {timeContracts.length === 0 && (
            <div className="py-8 text-center text-muted-foreground text-sm">{t('semanticCatalog.l2Extended.noTimeContracts')}</div>
          )}
        </>
      )}

      {/* ═══════ 접근 정책 테이블 ═══════ */}
      {subTab === 'access-policies' && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.entityId')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.policyType')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.condition')}</th>
                <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.targetRoles')}</th>
                <th className="px-3 py-2 text-center font-medium">{t('semanticCatalogExt.activeCol')}</th>
              </tr>
            </thead>
            <tbody>
              {accessPolicies.map((ap) => {
                const typeBadge = ACCESS_POLICY_COLORS[ap.policy_type] ?? 'bg-slate-100 text-slate-700';
                return (
                  <tr key={ap.access_policy_id} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{ap.entity_id}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${typeBadge}`}>
                        {ap.policy_type}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground max-w-[300px] truncate" title={ap.condition_expression}>
                      {ap.condition_expression}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {ap.target_roles.map((role) => (
                          <span key={role} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                            {role}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-center">
                      {ap.is_active ? (
                        <span className="text-green-600 text-xs font-medium">{t('semanticCatalogExt.active')}</span>
                      ) : (
                        <span className="text-red-600 text-xs">{t('semanticCatalogExt.inactive')}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {accessPolicies.length === 0 && (
            <div className="py-8 text-center text-muted-foreground text-sm">{t('semanticCatalog.l2Extended.noAccessPolicies')}</div>
          )}
        </>
      )}
    </div>
  );
}
