/**
 * WizardStepReview — Step 3: 검토 + 생성
 * 매핑 미리보기, 온톨로지 이름/설명 설정, 인과 추론 옵션, "생성" 버튼
 * 생성 완료 후 결과 요약 표시
 */
import { ChevronLeft, Loader2, Check, Sparkles, AlertCircle } from 'lucide-react';
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
          <h3 className="text-lg font-semibold text-foreground">온톨로지 생성 완료</h3>
          <p className="text-sm text-muted-foreground">
            {generationResult.tablesProcessed}개 테이블에서{' '}
            {generationResult.nodes.length}개 노드,{' '}
            {generationResult.relationships.length}개 관계가 생성되었습니다.
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
            닫기
          </button>
          <button
            type="button"
            onClick={reset}
            className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            새 온톨로지 만들기
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
          <h3 className="text-lg font-semibold text-foreground">검토 및 생성</h3>
          <p className="text-sm text-muted-foreground">매핑을 확인하고 온톨로지를 생성하세요</p>
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
        <span className="text-xs text-muted-foreground ml-auto">{mappings.length}개 테이블</span>
      </div>

      {/* 온톨로지 이름 */}
      <div className="space-y-1.5">
        <label className="text-sm font-medium text-foreground">온톨로지 이름</label>
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
        <label className="text-sm font-medium text-foreground">설명 (선택)</label>
        <textarea
          value={ontologyDescription}
          onChange={(e) => setOntologyDescription(e.target.value)}
          placeholder="온톨로지에 대한 설명..."
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
          <span className="text-sm text-foreground font-medium">인과관계 자동 추론</span>
          <p className="text-xs text-muted-foreground">테이블 간 FK 관계와 레이어 구조를 분석하여 인과관계를 자동 생성합니다</p>
        </div>
      </label>

      {/* 매핑 미리보기 */}
      <div className="border border-border rounded-lg overflow-hidden bg-card">
        <div className="px-4 py-2.5 bg-muted/50 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          매핑 미리보기
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
            {generationError instanceof Error ? generationError.message : '온톨로지 생성에 실패했습니다'}
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
          이전
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
              생성 중...
            </>
          ) : (
            <>
              <Sparkles size={14} />
              온톨로지 생성
            </>
          )}
        </button>
      </div>
    </div>
  );
}
