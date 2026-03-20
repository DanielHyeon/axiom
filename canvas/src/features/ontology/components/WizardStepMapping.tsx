/**
 * WizardStepMapping — Step 2: 레이어 매핑
 * 각 선택된 테이블을 온톨로지 5계층(KPI/Driver/Measure/Process/Resource)에 매핑
 * 자동 추천 후 사용자가 수동 조정 가능
 */
import { ChevronLeft, ArrowRight } from 'lucide-react';
import type { OntologyLayer } from '../types/ontology';
import type { useOntologyWizard } from '../hooks/useOntologyWizard';

type WizardHook = ReturnType<typeof useOntologyWizard>;

interface Props {
  wizard: WizardHook;
}

// 레이어 설정: 라벨, 색상, 설명
const LAYERS: { key: OntologyLayer; label: string; color: string; description: string }[] = [
  { key: 'kpi', label: 'KPI', color: 'bg-red-100 text-red-700 border-red-200 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30', description: '핵심 성과 지표' },
  { key: 'driver', label: 'Driver', color: 'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-500/15 dark:text-orange-400 dark:border-orange-500/30', description: '변동 원인 요인' },
  { key: 'measure', label: 'Measure', color: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-500/15 dark:text-blue-400 dark:border-blue-500/30', description: '측정 지표' },
  { key: 'process', label: 'Process', color: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-500/15 dark:text-green-400 dark:border-green-500/30', description: '비즈니스 프로세스' },
  { key: 'resource', label: 'Resource', color: 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-500/15 dark:text-purple-400 dark:border-purple-500/30', description: '물리적/논리적 자원' },
];

export function WizardStepMapping({ wizard }: Props) {
  const { mappings, updateMappingLayer, goBack, goToReview } = wizard;

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={goBack}
          className="p-1.5 rounded hover:bg-muted text-muted-foreground"
        >
          <ChevronLeft size={16} />
        </button>
        <div>
          <h3 className="text-lg font-semibold text-foreground">레이어 매핑</h3>
          <p className="text-sm text-muted-foreground">각 테이블을 온톨로지 레이어에 매핑하세요. 자동 추천된 레이어를 확인 후 수정할 수 있습니다.</p>
        </div>
      </div>

      {/* 레이어 범례 */}
      <div className="flex flex-wrap gap-2 p-3 bg-muted/30 rounded-lg">
        {LAYERS.map((l) => (
          <span
            key={l.key}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${l.color}`}
          >
            {l.label}
            <span className="text-[10px] font-normal opacity-75">- {l.description}</span>
          </span>
        ))}
      </div>

      {/* 매핑 테이블 */}
      <div className="border border-border rounded-lg overflow-hidden bg-card">
        <div className="grid grid-cols-[1fr_40px_1fr] items-center px-4 py-2.5 bg-muted/50 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          <span>테이블</span>
          <span />
          <span>레이어</span>
        </div>
        <div className="divide-y divide-border max-h-[400px] overflow-y-auto">
          {mappings.map((m) => (
            <div
              key={m.tableName}
              className="grid grid-cols-[1fr_40px_1fr] items-center px-4 py-3 hover:bg-muted/20 transition-colors"
            >
              {/* 테이블 이름 */}
              <div>
                <p className="text-sm font-medium text-foreground">{m.tableName}</p>
                {m.columns && m.columns.length > 0 && (
                  <p className="text-[10px] text-muted-foreground mt-0.5 truncate max-w-[200px]">
                    {m.columns.slice(0, 4).join(', ')}
                    {m.columns.length > 4 ? ` +${m.columns.length - 4}` : ''}
                  </p>
                )}
              </div>

              {/* 화살표 */}
              <div className="flex justify-center">
                <ArrowRight size={14} className="text-muted-foreground" />
              </div>

              {/* 레이어 선택 */}
              <div className="flex flex-wrap gap-1.5">
                {LAYERS.map((l) => (
                  <button
                    key={l.key}
                    type="button"
                    onClick={() => updateMappingLayer(m.tableName, l.key)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                      m.layer === l.key
                        ? `${l.color} border ring-1 ring-offset-1 ring-current`
                        : 'bg-secondary text-muted-foreground border border-transparent hover:border-border'
                    }`}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 요약 */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        {LAYERS.map((l) => {
          const count = mappings.filter((m) => m.layer === l.key).length;
          if (count === 0) return null;
          return (
            <span key={l.key} className="flex items-center gap-1">
              <span className={`w-2 h-2 rounded-full ${l.color.split(' ')[0]}`} />
              {l.label}: {count}
            </span>
          );
        })}
      </div>

      {/* 다음 단계 */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={goToReview}
          className="px-5 py-2.5 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90 transition-colors"
        >
          검토 및 생성
        </button>
      </div>
    </div>
  );
}
