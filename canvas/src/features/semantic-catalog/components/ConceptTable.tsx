/**
 * 온톨로지 개념 테이블 — 개념 목록 + 상태 전이 + 용어 표시
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronRight, Tag, Shield } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import type { OntologyConcept, ConceptStatus } from '../types/semantic';

interface Props {
  concepts: OntologyConcept[];
  onStatusChange?: (conceptId: string, newStatus: ConceptStatus) => void;
  isStatusChanging?: boolean;
}

export function ConceptTable({ concepts, onStatusChange, isStatusChanging }: Props) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="rounded-lg border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="w-8 px-3 py-2" />
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.conceptId')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.conceptName')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.domain')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.ownerTeam')}</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.status')}</th>
            <th className="px-3 py-2 text-center font-medium">v</th>
            <th className="px-3 py-2 text-left font-medium">{t('semanticCatalogExt.sensitivity')}</th>
          </tr>
        </thead>
        <tbody>
          {concepts.map((c) => {
            const isExpanded = expandedId === c.concept_id;
            return (
              <>
                <tr
                  key={c.concept_id}
                  className="border-b hover:bg-muted/30 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : c.concept_id)}
                >
                  <td className="px-3 py-2">
                    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{c.concept_id}</td>
                  <td className="px-3 py-2 font-medium">{c.name_ko}</td>
                  <td className="px-3 py-2 text-muted-foreground">{c.domain_id}</td>
                  <td className="px-3 py-2 text-muted-foreground">{c.owner_team || '—'}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-3 py-2 text-center tabular-nums">{c.version}</td>
                  <td className="px-3 py-2">
                    {c.sensitivity_level === 'confidential' || c.sensitivity_level === 'restricted' ? (
                      <Shield className="h-4 w-4 text-red-500" />
                    ) : (
                      <span className="text-muted-foreground text-xs">{c.sensitivity_level}</span>
                    )}
                  </td>
                </tr>
                {/* 확장 영역: 비즈니스 정의 + 용어 + 상태 전이 */}
                {isExpanded && (
                  <tr key={`${c.concept_id}-detail`} className="bg-muted/20">
                    <td colSpan={8} className="px-6 py-3">
                      <div className="space-y-2">
                        {c.business_definition && (
                          <p className="text-sm text-muted-foreground">{c.business_definition}</p>
                        )}
                        {c.terms && c.terms.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {c.terms.map((t) => (
                              <span
                                key={t.term_id}
                                className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                              >
                                <Tag className="h-3 w-3" />
                                {t.surface_form}
                                <span className="text-blue-400">({t.language})</span>
                              </span>
                            ))}
                          </div>
                        )}
                        {/* 상태 전이 버튼 */}
                        {onStatusChange && c.status === 'draft' && (
                          <button
                            className="text-xs px-2 py-1 rounded bg-yellow-100 hover:bg-yellow-200 text-yellow-800"
                            disabled={isStatusChanging}
                            onClick={(e) => { e.stopPropagation(); onStatusChange(c.concept_id, 'review'); }}
                          >
                            {t('semanticCatalogExt.requestReview')}
                          </button>
                        )}
                        {onStatusChange && c.status === 'review' && (
                          <button
                            className="text-xs px-2 py-1 rounded bg-green-100 hover:bg-green-200 text-green-800"
                            disabled={isStatusChanging}
                            onClick={(e) => { e.stopPropagation(); onStatusChange(c.concept_id, 'approved'); }}
                          >
                            Approve
                          </button>
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
      {concepts.length === 0 && (
        <div className="py-8 text-center text-muted-foreground text-sm">{t('semanticCatalogExt.noConcepts')}</div>
      )}
    </div>
  );
}
