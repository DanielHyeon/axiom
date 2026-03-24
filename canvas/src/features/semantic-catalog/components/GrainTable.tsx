/**
 * 그레인 계약 테이블 — 엔티티별 행 단위 유일성 규칙
 */
import { useTranslation } from 'react-i18next';
import { Key, Clock, AlertTriangle } from 'lucide-react';
import type { GrainContract } from '../types/semantic';

interface Props {
  grains: GrainContract[];
}

const RESOLUTION_LABELS: Record<string, { label: string; className: string }> = {
  fail: { label: 'Fail on dup', className: 'bg-red-50 text-red-700' },
  latest_wins: { label: 'Latest wins', className: 'bg-amber-50 text-amber-700' },
  aggregate: { label: 'Aggregate', className: 'bg-blue-50 text-blue-700' },
};

export function GrainTable({ grains }: Props) {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.grainId')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.entity')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.keySet')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.timeGrain')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.duplicateResolution')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.validationExpr')}</th>
            <th className="px-3 py-2 text-center font-medium">v</th>
          </tr>
        </thead>
        <tbody>
          {grains.map((g) => {
            const keys = Array.isArray(g.grain_key_set) ? g.grain_key_set : [];
            const res = RESOLUTION_LABELS[g.duplicate_resolution_rule] ?? RESOLUTION_LABELS.fail;
            return (
              <tr key={g.grain_id} className="border-b hover:bg-muted/30">
                <td className="px-3 py-2 font-mono text-xs">{g.grain_id}</td>
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{g.entity_id}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {keys.map((k) => (
                      <span key={k} className="inline-flex items-center gap-0.5 rounded bg-cyan-50 px-1.5 py-0.5 text-xs text-cyan-700">
                        <Key className="h-3 w-3" />
                        {k}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1 text-xs">
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    <span>{g.time_grain === 'none' ? '—' : g.time_grain}</span>
                  </div>
                </td>
                <td className="px-3 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-xs ${res.className}`}>
                    {res.label}
                  </span>
                </td>
                <td className="px-3 py-2">
                  {g.uniqueness_test ? (
                    <code className="text-xs bg-slate-100 rounded px-1.5 py-0.5">{g.uniqueness_test}</code>
                  ) : (
                    <div className="flex items-center gap-1 text-xs text-amber-600">
                      <AlertTriangle className="h-3 w-3" />
                      {t('semanticCatalogExt.undefined')}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2 text-center tabular-nums">{g.version}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {grains.length === 0 && (
        <div className="py-8 text-center text-muted-foreground text-sm">{t('semanticCatalogExt.noGrainContracts')}</div>
      )}
    </div>
  );
}
