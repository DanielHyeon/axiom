/**
 * WhatIfWizard — What-if 시뮬레이션 위자드 (리디자인)
 *
 * .pen 디자인 사양:
 * - 레이아웃: 좌우 수평 분할, 32px 패딩, 48px 좌우, 32px gap
 * - LEFT: Config Panel (360px)
 *   - "DAG Configuration" Sora 18px semibold
 *   - 설명: Geist 13px secondary, lineHeight 1.5
 *   - Parameter Card: 흰색, 12px radius, 16px padding, 12px gap
 *     - 파라미터 슬라이더: label + slider bar + value text
 *   - 버튼: Previous (outline) + Next Step (primary fill, 8px radius)
 * - RIGHT: Graph Canvas (fill, 흰색 카드, 12px radius)
 *   - "Causal DAG Preview" 라벨
 *   - 색상 노드: primary(Exchange Rate), blue(Revenue/Cost), green(OEE)
 *   - 화살표 아이콘
 *
 * 5단계 위자드 상태 관리는 기존 store를 그대로 유지.
 */
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { WIZARD_STEP_META } from '../types/whatifWizard.types';
import type { WizardStepNumber } from '../types/whatifWizard.types';

// 위자드 단계별 컴포넌트
import { Step1ScenarioDefine } from './Step1ScenarioDefine';
import { Step2DataSelect } from './Step2DataSelect';
import { Step3CausalDiscovery } from './Step3CausalDiscovery';
import { Step4Intervention } from './Step4Intervention';
import { Step5ResultCompare } from './Step5ResultCompare';

export function WhatIfWizard() {
  const { t } = useTranslation();
  const store = useWhatIfWizardStore();
  const {
    currentStep,
    nextStep,
    prevStep,
    canProceed,
    interventions,
    causalRelations,
    selectedNodes,
  } = store;

  const isFirst = currentStep === 1;
  const isLast = currentStep === 5;
  const stepMeta = WIZARD_STEP_META[currentStep];

  // 현재 단계 콘텐츠 렌더링
  const renderStepContent = useCallback(() => {
    switch (currentStep) {
      case 1: return <Step1ScenarioDefine />;
      case 2: return <Step2DataSelect />;
      case 3: return <Step3CausalDiscovery />;
      case 4: return <Step4Intervention />;
      case 5: return <Step5ResultCompare />;
      default: return null;
    }
  }, [currentStep]);

  return (
    <div className="flex h-full bg-background text-foreground overflow-hidden">
      {/* LEFT — Config Panel (360px) */}
      <div className="w-[360px] shrink-0 flex flex-col gap-5 py-8 px-12 overflow-y-auto">
        {/* 단계 제목 — Sora 18px semibold */}
        <h1 className="font-heading text-lg font-semibold text-foreground">
          {stepMeta.label}
        </h1>

        {/* 단계 설명 — Geist 13px secondary, lineHeight 1.5 */}
        <p className="text-[13px] text-text-secondary leading-relaxed">
          {stepMeta.description}
        </p>

        {/* 단계별 폼 콘텐츠 */}
        <div className="flex-1 flex flex-col gap-3">
          {renderStepContent()}
        </div>

        {/* 하단 네비게이션 버튼 */}
        <div className="flex items-center gap-3 mt-auto pt-4">
          {/* Previous 버튼 — outline 스타일 */}
          <button
            type="button"
            onClick={prevStep}
            disabled={isFirst}
            className={[
              'flex items-center justify-center h-10 px-5 rounded-lg border border-border',
              'text-[13px] font-medium text-text-secondary transition-colors',
              isFirst
                ? 'opacity-40 cursor-not-allowed'
                : 'hover:bg-muted cursor-pointer',
            ].join(' ')}
          >
            <ChevronLeft size={14} className="mr-1" />
            {t('whatifWizard.prev', 'Previous')}
          </button>

          {/* Next Step 버튼 — primary fill */}
          {!isLast && (
            <button
              type="button"
              onClick={nextStep}
              disabled={!canProceed()}
              className={[
                'flex-1 flex items-center justify-center h-10 px-5 rounded-lg',
                'text-[13px] font-semibold transition-colors',
                canProceed()
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer'
                  : 'bg-border text-text-placeholder cursor-not-allowed',
              ].join(' ')}
            >
              {t('whatifWizard.next', 'Next Step')}
              <ChevronRight size={14} className="ml-1" />
            </button>
          )}
        </div>
      </div>

      {/* RIGHT — Graph Canvas (fill) */}
      <div className="flex-1 flex items-center justify-center py-8 pr-12">
        <div className="w-full h-full bg-card rounded-xl border border-border flex flex-col items-center justify-center gap-3 p-6">
          {/* 그래프 제목 */}
          <span className="text-xs font-medium text-text-secondary">
            Causal DAG Preview
          </span>

          {/* DAG 노드 시각화 — 인과관계 기반 */}
          <CausalDagPreview
            selectedNodes={selectedNodes}
            causalRelations={causalRelations}
            interventions={interventions}
          />
        </div>
      </div>
    </div>
  );
}

// ── 인과 DAG 미리보기 컴포넌트 ──

interface CausalDagPreviewProps {
  selectedNodes: { id: string; name: string; type: string }[];
  causalRelations: { sourceId: string; sourceName: string; targetId: string; targetName: string; weight: number }[];
  interventions: { nodeId: string; nodeName: string; value: number }[];
}

/**
 * CausalDagPreview — 위자드 우측 패널의 DAG 시각화
 *
 * 디자인 사양:
 * - 최상단: 개입 노드 (주황색 #FF8400)
 * - 중간: 중간 노드 (파란색 #3B82F6)
 * - 최하단: 타깃 KPI 노드 (녹색 #22C55E)
 * - 노드 사이에 화살표 아이콘
 */
function CausalDagPreview({ selectedNodes, causalRelations, interventions }: CausalDagPreviewProps) {
  // 개입이 설정된 노드들 (주황색)
  const interventionNodeIds = new Set(interventions.map((iv) => iv.nodeId));

  // 인과관계에서 타깃이 되는 노드들 (녹색)
  const targetNodeIds = new Set(causalRelations.map((r) => r.targetId));

  // 인과관계에서 소스가 되는 노드들 (파란색 중간)
  const sourceNodeIds = new Set(causalRelations.map((r) => r.sourceId));

  // 노드 없으면 기본 예제 표시
  if (selectedNodes.length === 0 && causalRelations.length === 0) {
    return <DefaultDagPreview />;
  }

  // 계층 분류
  const topNodes = selectedNodes.filter((n) => interventionNodeIds.has(n.id));
  const midNodes = selectedNodes.filter(
    (n) => !interventionNodeIds.has(n.id) && sourceNodeIds.has(n.id),
  );
  const bottomNodes = selectedNodes.filter(
    (n) => !interventionNodeIds.has(n.id) && targetNodeIds.has(n.id) && !sourceNodeIds.has(n.id),
  );

  // 분류되지 않은 나머지 노드
  const classifiedIds = new Set([...topNodes, ...midNodes, ...bottomNodes].map((n) => n.id));
  const unclassified = selectedNodes.filter((n) => !classifiedIds.has(n.id));

  return (
    <div className="flex flex-col items-center gap-10">
      {/* 상위 — 개입 노드 (주황) */}
      {topNodes.length > 0 && (
        <>
          <div className="flex items-center gap-10">
            {topNodes.map((n) => (
              <DagNode key={n.id} name={n.name} color="orange" />
            ))}
          </div>
          <ArrowDown size={20} className="text-text-tertiary" />
        </>
      )}

      {/* 중간 — 중간 노드 (파랑) */}
      {(midNodes.length > 0 || unclassified.length > 0) && (
        <>
          <div className="flex items-center gap-10">
            {midNodes.map((n) => (
              <DagNode key={n.id} name={n.name} color="blue" />
            ))}
            {unclassified.map((n) => (
              <DagNode key={n.id} name={n.name} color="blue" />
            ))}
          </div>
          {bottomNodes.length > 0 && (
            <ArrowDown size={20} className="text-text-tertiary" />
          )}
        </>
      )}

      {/* 하위 — 타깃 KPI (녹색) */}
      {bottomNodes.length > 0 && (
        <div className="flex items-center gap-10">
          {bottomNodes.map((n) => (
            <DagNode key={n.id} name={n.name} color="green" />
          ))}
        </div>
      )}
    </div>
  );
}

/** 기본 예제 DAG (노드 미선택 시) */
function DefaultDagPreview() {
  return (
    <div className="flex flex-col items-center gap-10">
      <DagNode name="Exchange Rate" color="orange" />
      <ArrowDown size={20} className="text-text-tertiary" />
      <div className="flex items-center gap-10">
        <DagNode name="Revenue" color="blue" />
        <DagNode name="Cost" color="blue" />
      </div>
      <ArrowDown size={20} className="text-text-tertiary" />
      <DagNode name="OEE (Target KPI)" color="green" />
    </div>
  );
}

/** 개별 DAG 노드 */
function DagNode({ name, color }: { name: string; color: 'orange' | 'blue' | 'green' }) {
  /* 다크모드 대응 — 디자인 토큰 기반 색상 */
  const bgMap = {
    orange: 'bg-primary',
    blue: 'bg-accent-blue',
    green: 'bg-accent-green',
  };
  const textMap = {
    orange: 'text-primary-foreground',
    blue: 'text-white',
    green: 'text-white',
  };

  return (
    <div
      className={[
        bgMap[color],
        textMap[color],
        'px-5 py-2.5 rounded-lg text-xs font-semibold whitespace-nowrap',
      ].join(' ')}
    >
      {name}
    </div>
  );
}
