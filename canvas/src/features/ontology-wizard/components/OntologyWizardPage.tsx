/**
 * OntologyWizardPage — Deep Agents 멀티레이어 온톨로지 생성 위자드
 * 4단계 흐름: 입력 → SSE 스트리밍 생성 → 검토 → 완료
 *
 * Step 1 (입력): 텍스트 입력, 도메인 힌트, 레이어 체크박스
 * Step 2 (생성 중): 5개 레이어 카드에 실시간 진행률 표시
 * Step 3 (검토): 레이어별 노드 목록 + 통계 요약
 * Step 4 (완료): 성공 메시지 + 온톨로지 페이지 이동 버튼
 */
import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ArrowRight,
  Loader2,
  RotateCcw,
  ExternalLink,
  AlertCircle,
  XCircle,
  CheckCircle2,
  FileText,
  Layers,
} from 'lucide-react';
import { useMultiLayerWizard } from '../hooks/useMultiLayerWizard';
import { StepIndicator } from './StepIndicator';
import { LayerProgressCard } from './LayerProgressCard';
import type { TargetLayer } from '../types/wizard';
import { LAYER_LABELS } from '../types/wizard';

/** 선택 가능한 5계층 레이어 — 라벨은 t()로 런타임 조회 */
const ALL_LAYER_KEYS: TargetLayer[] = ['kpi', 'measure', 'driver', 'process', 'resource'];

export function OntologyWizardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const wizard = useMultiLayerWizard();

  // ─── Step 1: 입력 상태 ───
  const [inputText, setInputText] = useState('');
  const [domainHint, setDomainHint] = useState('');
  const [selectedLayers, setSelectedLayers] = useState<Set<TargetLayer>>(
    new Set(ALL_LAYER_KEYS),
  );

  /** 레이어 체크박스 토글 */
  const toggleLayer = (layer: TargetLayer) => {
    setSelectedLayers((prev) => {
      const next = new Set(prev);
      if (next.has(layer)) {
        // 최소 1개 레이어 필요
        if (next.size > 1) next.delete(layer);
      } else {
        next.add(layer);
      }
      return next;
    });
  };

  /** 전체 선택/해제 */
  const toggleAll = () => {
    if (selectedLayers.size === ALL_LAYER_KEYS.length) {
      // 모두 선택된 경우 → KPI만 남김
      setSelectedLayers(new Set(['kpi']));
    } else {
      setSelectedLayers(new Set(ALL_LAYER_KEYS));
    }
  };

  /** 생성 시작 가능 여부 */
  const canStart = inputText.trim().length >= 10 && selectedLayers.size > 0;

  /** 생성 시작 핸들러 */
  const handleStart = () => {
    if (!canStart) return;
    wizard.startGeneration(
      inputText.trim(),
      domainHint.trim() || undefined,
      Array.from(selectedLayers),
    );
  };

  /** 전체 진행률 계산 */
  const overallProgress = useMemo(() => {
    if (wizard.layerProgress.size === 0) return 0;
    let total = 0;
    wizard.layerProgress.forEach((lp) => {
      total += lp.progress;
    });
    return Math.round(total / wizard.layerProgress.size);
  }, [wizard.layerProgress]);

  /** 위자드 초기화 + 입력 상태 초기화 */
  const handleReset = () => {
    wizard.reset();
    setInputText('');
    setDomainHint('');
    setSelectedLayers(new Set(ALL_LAYER_KEYS));
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-8">
        {/* 페이지 제목 */}
        <div className="flex items-center gap-3 mb-4 md:mb-6">
          <div className="p-2 rounded-lg bg-primary/10 shrink-0">
            <Sparkles size={24} className="text-primary" />
          </div>
          <div>
            <h1 className="text-xl md:text-2xl font-bold text-foreground">
              {t('ontologyWizardExt.title')}
            </h1>
            <p className="text-xs md:text-sm text-muted-foreground">
              {t('ontologyWizardExt.subtitle')}
            </p>
          </div>
        </div>

        {/* 단계 표시기 */}
        <div className="mb-4 md:mb-8 p-3 md:p-4 bg-card border border-border rounded-xl overflow-x-auto">
          <StepIndicator currentStep={wizard.step} />
        </div>

        {/* ─── Step 1: 입력 ─── */}
        {wizard.step === 'INPUT' && (
          <div className="space-y-6">
            {/* 입력 텍스트 */}
            <div className="bg-card border border-border rounded-xl p-4 md:p-6">
              <div className="flex items-center gap-2 mb-3">
                <FileText size={18} className="text-primary" />
                <h3 className="text-sm md:text-base font-semibold text-foreground">
                  {t('ontologyWizardExt.inputText')}
                </h3>
              </div>
              <p className="text-xs md:text-sm text-muted-foreground mb-3">
                {t('ontologyWizardExt.inputHint')}
              </p>
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={t('ontologyWizardExt.inputPlaceholder')}
                className="w-full min-h-[180px] p-4 rounded-lg border border-border bg-background text-foreground placeholder:text-muted-foreground resize-y focus:outline-none focus:ring-2 focus:ring-primary/40 text-sm leading-relaxed"
              />
              <div className="flex justify-end mt-1">
                <span className={`text-xs ${inputText.length < 10 ? 'text-muted-foreground' : 'text-green-600'}`}>
                  {t('ontologyWizardExt.charCount', { count: inputText.length })}
                </span>
              </div>
            </div>

            {/* 도메인 힌트 */}
            <div className="bg-card border border-border rounded-xl p-6">
              <h3 className="text-base font-semibold text-foreground mb-2">
                {t('ontologyWizardExt.domainHint')}
              </h3>
              <p className="text-sm text-muted-foreground mb-3">
                {t('ontologyWizardExt.domainHintDesc')}
              </p>
              <input
                type="text"
                value={domainHint}
                onChange={(e) => setDomainHint(e.target.value)}
                placeholder={t('ontologyWizardExt.domainHintPlaceholder')}
                className="w-full p-3 rounded-lg border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 text-sm"
              />
            </div>

            {/* 레이어 선택 */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Layers size={18} className="text-primary" />
                  <h3 className="text-base font-semibold text-foreground">
                    {t('ontologyWizardExt.targetLayers')}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={toggleAll}
                  className="text-xs text-primary hover:underline"
                >
                  {selectedLayers.size === ALL_LAYER_KEYS.length ? t('ontologyWizardExt.selectMin') : t('ontologyWizardExt.selectAll')}
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {ALL_LAYER_KEYS.map((layerKey) => {
                  const checked = selectedLayers.has(layerKey);
                  return (
                    <label
                      key={layerKey}
                      className={`
                        flex items-center gap-2.5 p-3 rounded-lg border cursor-pointer
                        transition-colors duration-200
                        ${checked
                          ? 'bg-primary/5 border-primary/30'
                          : 'bg-background border-border hover:bg-muted/50'
                        }
                      `}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleLayer(layerKey)}
                        className="w-4 h-4 rounded border-border text-primary focus:ring-primary/40"
                      />
                      <span className="text-sm text-foreground">{t(`ontologyWizardExt.layers.${layerKey}`)}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* 시작 버튼 */}
            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleStart}
                disabled={!canStart}
                className="
                  inline-flex items-center gap-2 px-6 py-3 rounded-lg
                  bg-primary text-primary-foreground font-medium text-sm
                  hover:bg-primary/90 transition-colors
                  disabled:opacity-50 disabled:cursor-not-allowed
                "
              >
                <Sparkles size={16} />
                {t('ontologyWizardExt.startGeneration')}
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* ─── Step 2: 생성 중 ─── */}
        {wizard.step === 'GENERATING' && (
          <div className="space-y-6">
            {/* 전체 진행률 */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Loader2 size={18} className="text-primary animate-spin" />
                  <h3 className="text-base font-semibold text-foreground">
                    {t('ontologyWizardExt.generating')}
                  </h3>
                </div>
                <span className="text-sm font-mono text-muted-foreground">
                  {overallProgress}%
                </span>
              </div>
              <div className="h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-primary to-primary/70 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${overallProgress}%` }}
                />
              </div>
            </div>

            {/* 레이어별 진행 카드 */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from(wizard.layerProgress.values()).map((lp) => (
                <LayerProgressCard key={lp.layer} progress={lp} />
              ))}
            </div>

            {/* 에러 표시 */}
            {wizard.error && (
              <div className="flex items-start gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
                <AlertCircle size={18} className="text-destructive mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-destructive">{t('ontologyWizardExt.errorOccurred')}</p>
                  <p className="text-sm text-destructive/80 mt-1">{wizard.error}</p>
                </div>
              </div>
            )}

            {/* 중단 버튼 */}
            <div className="flex justify-center">
              <button
                type="button"
                onClick={wizard.abort}
                className="
                  inline-flex items-center gap-2 px-5 py-2.5 rounded-lg
                  border border-destructive/30 text-destructive text-sm font-medium
                  hover:bg-destructive/5 transition-colors
                "
              >
                <XCircle size={16} />
                {t('ontologyWizardExt.abortGeneration')}
              </button>
            </div>
          </div>
        )}

        {/* ─── Step 3: 검토 ─── */}
        {wizard.step === 'REVIEW' && wizard.result && (
          <div className="space-y-6">
            {/* 요약 통계 */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle2 size={20} className="text-green-500" />
                <h3 className="text-base font-semibold text-foreground">
                  {t('ontologyWizardExt.generationComplete')}
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4">
                <div className="p-3 md:p-4 rounded-lg bg-blue-50 border border-blue-200">
                  <p className="text-xl md:text-2xl font-bold text-blue-700">
                    {wizard.result.totalNodes}
                  </p>
                  <p className="text-sm text-blue-600">{t('ontologyWizardExt.totalNodes')}</p>
                </div>
                <div className="p-3 md:p-4 rounded-lg bg-green-50 border border-green-200">
                  <p className="text-xl md:text-2xl font-bold text-green-700">
                    {wizard.result.totalRelations}
                  </p>
                  <p className="text-sm text-green-600">{t('ontologyWizardExt.totalRelations')}</p>
                </div>
              </div>
            </div>

            {/* 레이어별 노드 목록 */}
            <div className="space-y-4">
              {wizard.result.layerSchemas.map((schema) => (
                <div
                  key={schema.layer}
                  className="bg-card border border-border rounded-xl overflow-hidden"
                >
                  <div className="flex items-center justify-between px-6 py-3 bg-muted/50 border-b border-border">
                    <h4 className="text-sm font-semibold text-foreground">
                      {LAYER_LABELS[schema.layer] ?? schema.layer}
                    </h4>
                    <span className="text-xs text-muted-foreground">
                      {t('ontologyWizardExt.nodeCount', { count: schema.nodes.length, relCount: schema.relations.length })}
                    </span>
                  </div>
                  <div className="p-4">
                    {schema.nodes.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {schema.nodes.map((node) => (
                          <span
                            key={node.id}
                            className="inline-flex items-center px-3 py-1.5 rounded-md bg-muted text-sm text-foreground border border-border"
                            title={`ID: ${node.id}`}
                          >
                            {node.label}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground italic">
                        {t('ontologyWizardExt.noNodesGenerated')}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* 액션 버튼 */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
              <button
                type="button"
                onClick={handleReset}
                className="
                  inline-flex items-center justify-center gap-2 px-4 md:px-5 py-2.5 rounded-lg
                  border border-border text-foreground text-sm font-medium
                  hover:bg-muted transition-colors
                "
              >
                <RotateCcw size={16} />
                {t('ontologyWizardExt.regenerate')}
              </button>
              <button
                type="button"
                onClick={() => wizard.step === 'REVIEW' && navigate('/data/ontology')}
                className="
                  inline-flex items-center justify-center gap-2 px-4 md:px-6 py-2.5 md:py-3 rounded-lg
                  bg-primary text-primary-foreground font-medium text-sm
                  hover:bg-primary/90 transition-colors
                "
              >
                {t('ontologyWizardExt.viewOntology')}
                <ExternalLink size={16} />
              </button>
            </div>
          </div>
        )}

        {/* ─── Step 4: 완료 (에러 후 복구 등) ─── */}
        {wizard.step === 'INPUT' && wizard.error && (
          <div className="mt-4 flex items-start gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
            <AlertCircle size={18} className="text-destructive mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-destructive">{t('ontologyWizardExt.prevErrorTitle')}</p>
              <p className="text-sm text-destructive/80 mt-1">{wizard.error}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
