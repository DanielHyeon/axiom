/**
 * WizardStepReview — Step 3: 검토 + 생성
 * 매핑 미리보기, 온톨로지 이름/설명 설정, 인과 추론 옵션, "생성" 버튼
 * 생성 완료 후 결과 요약 표시
 */
import { ChevronLeft, Loader2, Check, Sparkles, AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { useOntologyWizard } from '../hooks/useOntologyWizard';
import type { OntologyLayer } from '../types/ontology';

type WizardHook = ReturnType<typeof useOntologyWizard>;

interface Props {
  wizard: WizardHook;
  onClose?: () => void;
}

// 레이어 색상 맵
const LAYER_COLORS: Record<OntologyLayer, string> = {
  kpi: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400',
  driver: 'bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-400',
  measure: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400',
  process: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-400',
  resource: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-400',
};

export function WizardStepReview({ wizard, onClose }: Props) {
  const { t } = useTranslation();
  const {
    mappings,
    selectedDatasource,
    selectedSchema,
    ontologyName,
    setOntologyName,
    ontologyDescription,
    setOntologyDescription,
    inferCausal,
    setInferCausal,
    generate,
    isGenerating,
    generationResult,
    generationError,
    goBack,
    reset,
  } = wizard;

  // 생성 완료 시
  if (generationResult) {
    return (
      <div className="flex flex-col items-center justify-center py-8 space-y-6">
        <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-500/15 flex items-center justify-center">
          <Check size={28} className="text-green-600" />
        </div>
        <div className="text-center space-y-1">
          <h3 className="text-lg font-semibold text-foreground">{t('ontologyExt.wizard.generationComplete')}</h3>
          <p className="text-sm text-muted-foreground">
            {t('ontologyExt.wizard.generationSummary', {
              tables: generationResult.tablesProcessed,
              nodes: generationResult.nodes.length,
              relations: generationResult.relationships.length,
            })}
          </p>
        </div>

        {/* 생성 결과 요약 */}
        <div className="w-full max-w-md border border-border rounded-lg divide-y divide-border bg-card">
          {generationResult.nodes.map((node) => (
            <div key={node.id} className="flex items-center gap-3 px-4 py-2.5">
              <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${LAYER_COLORS[node.layer]}`}>
                {node.layer.toUpperCase()}
              </span>
              <span className="text-sm text-foreground font-medium flex-1">{node.name}</span>
              <span className="text-xs text-muted-foreground">{node.sourceTable}</span>
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => { reset(); onClose?.(); }}
            className="px-4 py-2 text-sm border border-border rounded-md text-muted-foreground hover:bg-muted transition-colors"
          >
            {t('common.close')}
          </button>
          <button
            type="button"
            onClick={reset}
            className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            {t('ontologyExt.wizard.createNew')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
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
          <h3 className="text-lg font-semibold text-foreground">{t('ontologyExt.wizard.reviewAndCreate')}</h3>
          <p className="text-sm text-muted-foreground">{t('ontologyExt.wizard.reviewHint')}</p>
        </div>
      </div>

      {/* 소스 정보 */}
      <div className="flex items-center gap-2 p-3 bg-muted/30 rounded-lg">
        <span className="px-2 py-0.5 bg-primary text-primary-foreground rounded text-xs font-medium">
          {selectedDatasource}
        </span>
        <span className="text-xs text-muted-foreground">/</span>
        <span className="px-2 py-0.5 bg-primary text-primary-foreground rounded text-xs font-medium">
          {selectedSchema}
        </span>
        <span className="text-xs text-muted-foreground ml-auto">{t('ontologyExt.wizard.tableCount', { count: mappings.length })}</span>
      </div>

      {/* 온톨로지 이름 */}
      <div className="space-y-1.5">
        <label className="text-sm font-medium text-foreground">{t('ontologyExt.wizard.ontologyName')}</label>
        <input
          type="text"
          value={ontologyName}
          onChange={(e) => setOntologyName(e.target.value)}
          placeholder={`${selectedSchema} Ontology`}
          className="w-full px-3 py-2.5 bg-card border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
        />
      </div>

      {/* 설명 */}
      <div className="space-y-1.5">
        <label className="text-sm font-medium text-foreground">{t('ontologyExt.wizard.descriptionOpt')}</label>
        <textarea
          value={ontologyDescription}
          onChange={(e) => setOntologyDescription(e.target.value)}
          placeholder={t('ontologyExt.wizard.descriptionPlaceholder')}
          rows={3}
          className="w-full px-3 py-2.5 bg-card border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-y"
        />
      </div>

      {/* 옵션 */}
      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={inferCausal}
          onChange={(e) => setInferCausal(e.target.checked)}
          className="w-4 h-4 accent-primary"
        />
        <div>
          <span className="text-sm text-foreground font-medium">{t('ontologyExt.wizard.causalInference')}</span>
          <p className="text-xs text-muted-foreground">{t('ontologyExt.wizard.causalInferenceDesc')}</p>
        </div>
      </label>

      {/* 매핑 미리보기 */}
      <div className="border border-border rounded-lg overflow-hidden bg-card">
        <div className="px-4 py-2.5 bg-muted/50 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          {t('ontologyExt.wizard.mappingPreview')}
        </div>
        <div className="divide-y divide-border max-h-48 overflow-y-auto">
          {mappings.map((m) => (
            <div key={m.tableName} className="flex items-center gap-3 px-4 py-2">
              <span className="text-sm text-foreground flex-1">{m.tableName}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${LAYER_COLORS[m.layer]}`}>
                {m.layer.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 에러 */}
      {generationError && (
        <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/30 rounded-lg">
          <AlertCircle size={16} className="text-destructive shrink-0 mt-0.5" />
          <p className="text-sm text-destructive">
            {generationError instanceof Error ? generationError.message : t('ontologyExt.wizard.generationFailed')}
          </p>
        </div>
      )}

      {/* 생성 버튼 */}
      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={goBack}
          className="px-4 py-2.5 text-sm border border-border rounded-md text-muted-foreground hover:bg-muted transition-colors"
        >
          {t('common.back')}
        </button>
        <button
          type="button"
          onClick={() => generate()}
          disabled={isGenerating}
          className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isGenerating ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              {t('ontologyExt.wizard.generating')}
            </>
          ) : (
            <>
              <Sparkles size={14} />
              {t('ontologyExt.wizard.generate')}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
