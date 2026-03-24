/**
 * 시멘틱 엔티티 테이블 — 엔티티 목록 + 물리 소스 + 그레인 정의 + 배포 액션
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronRight, Database, Rocket, Link } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import type { SemanticEntity } from '../types/semantic';

interface Props {
  entities: SemanticEntity[];
  onPublish?: (entityId: string) => void;
  isPublishing?: boolean;
}

export function EntityTable({ entities, onPublish, isPublishing }: Props) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="rounded-lg border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="w-8 px-3 py-2" />
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.entityId')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.physicalSource')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.type')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.conceptBinding')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.status')}</th>
            <th className="px-3 py-2 text-center font-medium">v</th>
            <th className="px-3 py-2 text-center font-medium">{t('semanticCatalogExt.action')}</th>
          </tr>
        </thead>
        <tbody>
          {entities.map((e) => {
            const isExpanded = expandedId === e.entity_id;
            return (
              <>
                <tr
                  key={e.entity_id}
                  className="border-b hover:bg-muted/30 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : e.entity_id)}
                >
                  <td className="px-3 py-2">
                    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{e.entity_id}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <Database className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      <span className="font-mono text-xs">{e.physical_source_ref}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs ${
                      e.entity_type === 'fact' ? 'bg-blue-50 text-blue-700' :
                      e.entity_type === 'dimension' ? 'bg-amber-50 text-amber-700' :
                      'bg-slate-50 text-slate-700'
                    }`}>
                      {e.entity_type}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {e.bound_concept_id ? (
                      <div className="flex items-center gap-1 text-xs">
                        <Link className="h-3 w-3 text-green-600" />
                        <span className="font-mono text-green-700">{e.bound_concept_id}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">{t('semanticCatalogExt.unbound')}</span>
                    )}
                  </td>
                  <td className="px-3 py-2"><StatusBadge status={e.status} /></td>
                  <td className="px-3 py-2 text-center tabular-nums">{e.version}</td>
                  <td className="px-3 py-2 text-center">
                    {onPublish && e.status !== 'approved' && (
                      <button
                        className="p-1 rounded hover:bg-muted"
                        title={t('semanticCatalogExt.publish')}
                        onClick={(ev) => { ev.stopPropagation(); onPublish(e.entity_id); }}
                        disabled={isPublishing}
                      >
                        <Rocket className="h-3.5 w-3.5 text-green-600" />
                      </button>
                    )}
                  </td>
                </tr>
                {isExpanded && (
                  <tr key={`${e.entity_id}-detail`} className="bg-muted/20">
                    <td colSpan={8} className="px-6 py-3">
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="font-medium text-muted-foreground">{t('semanticCatalogExt.grainDefinition')}:</span>
                          <p className="mt-0.5">{e.grain_definition || '—'}</p>
                        </div>
                        <div>
                          <span className="font-medium text-muted-foreground">PK:</span>
                          <p className="mt-0.5 font-mono">{e.primary_key_spec || '—'}</p>
                        </div>
                        {e.freshness_sla_minutes && (
                          <div>
                            <span className="font-medium text-muted-foreground">Freshness SLA:</span>
                            <p className="mt-0.5">{e.freshness_sla_minutes}{t('semanticCatalogExt.minutes')}</p>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
      {entities.length === 0 && (
        <div className="py-8 text-center text-muted-foreground text-sm">{t('semanticCatalog.entity.noEntities')}</div>
      )}
    </div>
  );
}
