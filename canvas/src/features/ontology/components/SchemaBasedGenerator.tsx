/**
 * SchemaBasedGenerator — 스키마 기반 온톨로지 자동 생성 (간편 모드)
 * KAIR SchemaBasedGenerator.vue를 이식
 * OntologyWizard와 달리, 데이터소스/스키마만 선택하면 자동으로 테이블 분석 + 레이어 매핑 + 생성까지 수행
 * "원클릭 자동 생성" 접근 방식
 */
import { useState } from 'react';
import { Loader2, Check, Sparkles, ChevronLeft, AlertCircle } from 'lucide-react';
import { useOntologyWizard } from '../hooks/useOntologyWizard';

interface Props {
  onClose: () => void;
  onGenerated?: () => void;
}

export function SchemaBasedGenerator({ onClose, onGenerated }: Props) {
  const wizard = useOntologyWizard();
  const {
    datasources,
    datasourcesLoading,
    selectedDatasource,
    setSelectedDatasource,
    schemas,
    schemasLoading,
    selectedSchema,
    setSelectedSchema,
    ontologyName,
    setOntologyName,
    ontologyDescription,
    setOntologyDescription,
    inferCausal,
    setInferCausal,
    isGenerating,
    generationResult,
    generationError,
  } = wizard;

  const [domainHint, setDomainHint] = useState('');

  // 자동 생성: 전체 테이블을 선택 → 매핑 → 생성을 동기적으로 수행
  const handleAutoGenerate = () => {
    // 3단계를 순차적으로 수행 (setTimeout 체이닝 제거 — 레이스 컨디션 방지)
    wizard.selectAllTables();
    wizard.goToMapping();
    wizard.generate();
  };

  // 생성 완료
  if (generationResult) {
    return (
      <div className="p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-green-100 dark:bg-green-500/15 flex items-center justify-center">
            <Check size={20} className="text-green-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">온톨로지 생성 완료</p>
            <p className="text-xs text-muted-foreground">
              {generationResult.tablesProcessed}개 테이블 처리, {generationResult.nodes.length}개 노드 생성
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => { onGenerated?.(); onClose(); }}
          className="w-full px-4 py-2.5 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90 transition-colors"
        >
          확인
        </button>
      </div>
    );
  }

  // 단계 1: 데이터소스 선택
  if (!selectedDatasource) {
    return (
      <div className="p-4 space-y-3">
        <h4 className="text-sm font-semibold text-foreground">데이터소스 선택</h4>
        {datasourcesLoading ? (
          <LoadingSmall message="로딩 중..." />
        ) : (
          <div className="space-y-1.5">
            {datasources.map((ds) => (
              <button
                key={ds.name}
                type="button"
                onClick={() => setSelectedDatasource(ds.name)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-border hover:border-primary hover:bg-primary/5 transition-colors text-left"
              >
                <span className="text-sm font-medium text-foreground">{ds.name}</span>
                <span className="text-xs text-muted-foreground ml-auto">{ds.type || 'DB'}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 단계 2: 스키마 선택
  if (!selectedSchema) {
    return (
      <div className="p-4 space-y-3">
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setSelectedDatasource('')} className="text-xs text-muted-foreground hover:text-foreground">
            <ChevronLeft size={14} />
          </button>
          <h4 className="text-sm font-semibold text-foreground">스키마 선택 ({selectedDatasource})</h4>
        </div>
        {schemasLoading ? (
          <LoadingSmall message="스키마 로딩 중..." />
        ) : (
          <div className="space-y-1.5">
            {schemas.map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => setSelectedSchema(s.name)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-border hover:border-primary hover:bg-primary/5 transition-colors text-left"
              >
                <span className="text-sm font-medium text-foreground">{s.name}</span>
                {s.tableCount != null && (
                  <span className="text-xs text-muted-foreground ml-auto">{s.tableCount}개</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 단계 3: 생성 옵션
  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => setSelectedSchema('')} className="text-xs text-muted-foreground hover:text-foreground">
          <ChevronLeft size={14} />
        </button>
        <h4 className="text-sm font-semibold text-foreground">자동 생성 옵션</h4>
      </div>

      {/* 소스 표시 */}
      <div className="flex items-center gap-1.5 p-2.5 bg-muted/30 rounded-lg">
        <span className="px-2 py-0.5 bg-primary text-primary-foreground rounded text-[10px] font-medium">{selectedDatasource}</span>
        <span className="text-xs text-muted-foreground">/</span>
        <span className="px-2 py-0.5 bg-primary text-primary-foreground rounded text-[10px] font-medium">{selectedSchema}</span>
      </div>

      {/* 이름 */}
      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">온톨로지 이름</label>
        <input
          type="text"
          value={ontologyName}
          onChange={(e) => setOntologyName(e.target.value)}
          placeholder={`${selectedSchema.charAt(0).toUpperCase() + selectedSchema.slice(1)} Ontology`}
          className="w-full px-3 py-2 bg-card border border-border rounded-md text-sm focus:outline-none focus:border-primary"
        />
      </div>

      {/* 설명 */}
      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">설명 (선택)</label>
        <textarea
          value={ontologyDescription}
          onChange={(e) => setOntologyDescription(e.target.value)}
          placeholder="온톨로지 설명..."
          rows={2}
          className="w-full px-3 py-2 bg-card border border-border rounded-md text-sm focus:outline-none focus:border-primary resize-y"
        />
      </div>

      {/* 도메인 힌트 */}
      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">도메인 힌트 (선택)</label>
        <input
          type="text"
          value={domainHint}
          onChange={(e) => setDomainHint(e.target.value)}
          placeholder="예: 제조업, 공급망 관리..."
          className="w-full px-3 py-2 bg-card border border-border rounded-md text-sm focus:outline-none focus:border-primary"
        />
      </div>

      {/* 옵션 */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={inferCausal}
          onChange={(e) => setInferCausal(e.target.checked)}
          className="w-3.5 h-3.5 accent-primary"
        />
        <span className="text-xs text-foreground">인과관계 자동 추론</span>
      </label>

      {/* 에러 */}
      {generationError && (
        <div className="flex items-start gap-2 p-2.5 bg-destructive/10 border border-destructive/30 rounded-lg">
          <AlertCircle size={14} className="text-destructive shrink-0 mt-0.5" />
          <p className="text-xs text-destructive">
            {generationError instanceof Error ? generationError.message : '생성 실패'}
          </p>
        </div>
      )}

      {/* 버튼 */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onClose}
          className="flex-1 px-3 py-2 text-sm border border-border rounded-md text-muted-foreground hover:bg-muted transition-colors"
        >
          취소
        </button>
        <button
          type="button"
          onClick={handleAutoGenerate}
          disabled={isGenerating}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {isGenerating ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              생성 중...
            </>
          ) : (
            <>
              <Sparkles size={14} />
              자동 생성
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function LoadingSmall({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 py-4 text-muted-foreground">
      <Loader2 size={14} className="animate-spin" />
      <span className="text-xs">{message}</span>
    </div>
  );
}
