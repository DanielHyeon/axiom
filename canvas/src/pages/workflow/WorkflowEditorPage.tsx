/**
 * WorkflowEditorPage — 워크플로 에디터 페이지 (디자인 리뉴얼)
 *
 * .pen 디자인 매칭:
 * - 수평 분할 레이아웃
 * - LEFT: Steps Panel (240px, right border, 16px 패딩, 12px 갭)
 *   - "Workflow Steps" Sora 12px semibold
 *   - 스텝 항목: 40px 높이, 12px 패딩, 8px 갭, 6px radius
 *     - 넘버 서클 (24x24, 컬러, 12px radius) + 스텝명 Geist 12px
 *     - 활성 스텝: bg #F5F5F5, 완료: blue/green 넘버
 * - RIGHT: Editor Canvas (fill, centered, 32px 패딩)
 *   - 스텝 타이틀: Sora 16px semibold
 *   - 설명: Geist 13px secondary, centered
 *   - Rule Card: 400px, 흰색, 12px radius, 20px 패딩
 *     - 체크박스 (green squares) + 규칙 텍스트 Geist 12px
 *
 * 기존 workflow-editor store/types 재사용
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useWorkflowEditorStore } from '@/features/workflow-editor/store/useWorkflowEditorStore';
import type { WorkflowNode } from '@/features/workflow-editor/types/workflowEditor.types';

// ── 기본 워크플로 스텝 (디자인 기준 4단계) ──
interface WorkflowStep {
  id: string;
  number: number;
  name: string;
  description: string;
  rules: string[];
}

const DEFAULT_STEPS: WorkflowStep[] = [
  {
    id: 'step-1',
    number: 1,
    name: 'Receive Request',
    description: 'Configure incoming data reception and initial parsing rules',
    rules: [
      'Validate request format (JSON/XML)',
      'Check authentication token',
      'Rate limit per tenant',
    ],
  },
  {
    id: 'step-2',
    number: 2,
    name: 'Validate Data',
    description: 'Configure validation rules and error handling for incoming data',
    rules: [
      'Required fields must not be null',
      'Date format must be ISO 8601',
      'Numeric ranges within bounds',
    ],
  },
  {
    id: 'step-3',
    number: 3,
    name: 'Process & Transform',
    description: 'Define data transformation and enrichment pipeline steps',
    rules: [
      'Apply business rule mappings',
      'Enrich with ontology context',
      'Generate audit trail entries',
    ],
  },
  {
    id: 'step-4',
    number: 4,
    name: 'Notify & Complete',
    description: 'Configure notifications and completion handlers for the workflow',
    rules: [
      'Send completion webhook',
      'Update case status',
      'Archive processed data',
    ],
  },
];

/** 넘버 서클 색상 결정 — 활성: primary, 완료: accent-blue, 미래: border/secondary */
function getNumberStyle(stepIdx: number, activeIdx: number) {
  if (stepIdx === activeIdx) {
    // 활성 스텝 — primary 배경, primary-foreground 텍스트
    return { bg: 'hsl(var(--primary))', text: 'hsl(var(--primary-foreground))' };
  }
  if (stepIdx < activeIdx) {
    // 완료 스텝 — accent-blue 배경, 흰 텍스트
    return { bg: 'hsl(var(--accent-blue))', text: '#FFF' };
  }
  // 미래 스텝 — border 배경, text-secondary 텍스트
  return { bg: 'hsl(var(--border))', text: 'hsl(var(--text-secondary))' };
}

export const WorkflowEditorPage: React.FC = () => {
  const { t } = useTranslation();

  // 스토어에서 노드 가져오기 (기존 데이터가 있으면 활용)
  const storeNodes = useWorkflowEditorStore((s) => s.nodes);

  // 활성 스텝 인덱스
  const [activeStepIdx, setActiveStepIdx] = useState(0);

  // 스토어 노드가 있으면 그것으로 스텝 생성, 없으면 기본 스텝 사용
  const steps: WorkflowStep[] =
    storeNodes.length > 0
      ? storeNodes.map((node: WorkflowNode, idx: number) => ({
          id: node.id,
          number: idx + 1,
          name: node.label,
          description: `Configure ${node.type} node settings`,
          rules: [],
        }))
      : DEFAULT_STEPS;

  const currentStep = steps[activeStepIdx];

  // 규칙 체크 상태
  const [checkedRules, setCheckedRules] = useState<Set<string>>(new Set());

  /** 체크 토글 */
  const toggleRule = (rule: string) => {
    setCheckedRules((prev) => {
      const next = new Set(prev);
      if (next.has(rule)) {
        next.delete(rule);
      } else {
        next.add(rule);
      }
      return next;
    });
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── LEFT: Steps Panel (240px, right border) ── */}
      <aside className="flex flex-col gap-3 w-[240px] shrink-0 border-r border-border p-4">
        {/* 패널 타이틀 — Sora 12px semibold */}
        <h3 className="text-xs font-semibold text-foreground font-heading">
          {t('workflowEditor.steps', 'Workflow Steps')}
        </h3>

        {/* 스텝 목록 */}
        <nav className="flex flex-col gap-3" role="list" aria-label="Workflow steps">
          {steps.map((step, idx) => {
            const isActive = idx === activeStepIdx;
            const numStyle = getNumberStyle(idx, activeStepIdx);

            return (
              <button
                type="button"
                key={step.id}
                onClick={() => setActiveStepIdx(idx)}
                role="listitem"
                className={[
                  'flex items-center gap-2 h-10 px-3 rounded-md transition-colors',
                  isActive ? 'bg-muted' : 'hover:bg-muted/60',
                ].join(' ')}
              >
                {/* 넘버 서클 — 24x24, 12px radius (full circle) */}
                <span
                  className="flex items-center justify-center w-6 h-6 rounded-full text-[11px] font-semibold shrink-0"
                  style={{ backgroundColor: numStyle.bg, color: numStyle.text }}
                >
                  {step.number}
                </span>
                {/* 스텝명 — Geist 12px */}
                <span
                  className={[
                    'text-xs truncate',
                    isActive ? 'text-foreground' : 'text-text-secondary',
                  ].join(' ')}
                >
                  {step.name}
                </span>
              </button>
            );
          })}
        </nav>
      </aside>

      {/* ── RIGHT: Editor Canvas (fill, centered) ── */}
      <div className="flex-1 min-w-0 flex flex-col items-center justify-center p-8 overflow-y-auto">
        {currentStep && (
          <>
            {/* 스텝 타이틀 — Sora 16px semibold */}
            <h2 className="text-base font-semibold text-foreground font-heading">
              Step {currentStep.number}: {currentStep.name}
            </h2>

            {/* 설명 — Geist 13px secondary, centered */}
            <p className="mt-4 text-[13px] text-text-secondary text-center max-w-[400px]">
              {currentStep.description}
            </p>

            {/* Rule Card — 400px, 흰색, 12px radius, 20px 패딩 */}
            {currentStep.rules.length > 0 && (
              <div className="mt-4 w-[400px] rounded-xl bg-card border border-border p-5">
                {/* 규칙 타이틀 */}
                <h4 className="text-[13px] font-semibold text-foreground mb-3">
                  {t('workflowEditor.validationRules', 'Validation Rules')}
                </h4>

                {/* 규칙 목록 — 체크박스 + 텍스트 */}
                <div className="flex flex-col gap-3">
                  {currentStep.rules.map((rule) => {
                    const isChecked = checkedRules.has(rule);

                    return (
                      <label
                        key={rule}
                        className="flex items-center gap-2 cursor-pointer group"
                      >
                        {/* 체크박스 — green square 디자인 */}
                        <span
                          className={[
                            'flex items-center justify-center w-4 h-4 rounded-[3px] shrink-0 transition-colors',
                            isChecked
                              ? 'bg-accent-green'
                              : 'border border-border group-hover:border-accent-green',
                          ].join(' ')}
                        >
                          {isChecked && (
                            <svg
                              className="w-2.5 h-2.5 text-white"
                              viewBox="0 0 12 12"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <polyline points="2 6 5 9 10 3" />
                            </svg>
                          )}
                        </span>
                        {/* 규칙 텍스트 — Geist 12px */}
                        <input
                          type="checkbox"
                          className="sr-only"
                          checked={isChecked}
                          onChange={() => toggleRule(rule)}
                        />
                        <span className="text-xs text-foreground">{rule}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 규칙이 없는 스텝일 때 (스토어 노드 사용 시) */}
            {currentStep.rules.length === 0 && (
              <div className="mt-4 w-[400px] rounded-xl bg-card border border-border p-5 text-center">
                <p className="text-xs text-text-placeholder">
                  {t(
                    'workflowEditor.noRules',
                    'No rules configured for this step yet.',
                  )}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
