import type { ReactStreamStep } from '@/features/nl2sql/api/oracleNl2sqlApi';
import type { ReactStepType } from '@/features/nl2sql/types/nl2sql';
import { cn } from '@/lib/utils';
import {
  TableProperties,
  Code,
  ShieldCheck,
  Wrench,
  Play,
  BarChart3,
  GitBranch,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface ReactProgressTimelineProps {
  steps: ReactStreamStep[];
  isRunning: boolean;
}

const STEP_ORDER: ReactStepType[] = [
  'select',
  'generate',
  'validate',
  'execute',
  'quality',
  'triage',
];

const STEP_META: Record<ReactStepType, { label: string; icon: LucideIcon }> = {
  select: { label: 'Select Tables', icon: TableProperties },
  generate: { label: 'Generate SQL', icon: Code },
  validate: { label: 'Validate', icon: ShieldCheck },
  fix: { label: 'Fix SQL', icon: Wrench },
  execute: { label: 'Execute', icon: Play },
  quality: { label: 'Quality Check', icon: BarChart3 },
  triage: { label: 'Triage', icon: GitBranch },
  result: { label: 'Result', icon: CheckCircle2 },
  error: { label: 'Error', icon: XCircle },
};

function extractSummary(step: ReactStreamStep): string {
  const d = step.data;
  if (!d) return '';
  switch (step.step) {
    case 'select': {
      const tables = d.tables as string[] | undefined;
      return tables ? `${tables.length} tables` : '';
    }
    case 'generate':
      return 'SQL generated';
    case 'validate':
      return String(d.status ?? '');
    case 'fix':
      return 'SQL fixed';
    case 'execute': {
      const count = d.row_count;
      return count != null ? `${count} rows` : '';
    }
    case 'quality': {
      const score = d.score;
      return score != null ? `score: ${Number(score).toFixed(2)}` : '';
    }
    case 'triage':
      return String(d.action ?? '');
    case 'error':
      return String(d.message ?? '').slice(0, 60);
    default:
      return '';
  }
}

export function ReactProgressTimeline({ steps, isRunning }: ReactProgressTimelineProps) {
  const receivedSteps = new Set(steps.map((s) => s.step));
  const lastStep = steps[steps.length - 1];
  const hasError = steps.some((s) => s.step === 'error');
  const hasResult = steps.some((s) => s.step === 'result');
  const currentIteration = lastStep?.iteration ?? 1;

  const stepDataMap = new Map<string, ReactStreamStep>();
  for (const s of steps) {
    stepDataMap.set(s.step, s);
  }

  return (
    <div className="rounded border border-neutral-800 bg-neutral-900/50 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-400">
          ReAct Loop {currentIteration > 1 ? `(iteration ${currentIteration})` : ''}
        </span>
        {hasResult && (
          <span className="text-xs text-green-400">Complete</span>
        )}
        {hasError && (
          <span className="text-xs text-red-400">Failed</span>
        )}
      </div>
      <div className="space-y-1">
        {STEP_ORDER.map((stepType) => {
          const stepData = stepDataMap.get(stepType);
          const isDone = !!stepData;
          const isActive = isRunning && !isDone && lastStep?.step !== 'error' && lastStep?.step !== 'result' && isNextStep(stepType, lastStep?.step);
          const meta = STEP_META[stepType];
          const Icon = meta.icon;
          const summary = stepData ? extractSummary(stepData) : '';
          const isErrorStep = stepType === lastStep?.step && hasError;

          return (
            <div key={stepType} className="flex items-center gap-2 py-0.5">
              <div
                className={cn(
                  'flex h-5 w-5 items-center justify-center rounded-full',
                  isDone && !isErrorStep && 'bg-green-900/50 text-green-400',
                  isActive && 'bg-blue-900/50 text-blue-400 animate-pulse',
                  isErrorStep && 'bg-red-900/50 text-red-400',
                  !isDone && !isActive && !isErrorStep && 'bg-neutral-800 text-neutral-600'
                )}
              >
                <Icon className="h-3 w-3" />
              </div>
              <span
                className={cn(
                  'text-xs',
                  isDone && !isErrorStep && 'text-neutral-300',
                  isActive && 'text-blue-300',
                  isErrorStep && 'text-red-300',
                  !isDone && !isActive && !isErrorStep && 'text-neutral-600'
                )}
              >
                {meta.label}
              </span>
              {summary && (
                <span className="text-xs text-neutral-500 ml-auto truncate max-w-[200px]">
                  {summary}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function isNextStep(candidate: ReactStepType, lastCompleted: string | undefined): boolean {
  if (!lastCompleted) return candidate === 'select';
  const idx = STEP_ORDER.indexOf(lastCompleted as ReactStepType);
  return idx >= 0 && STEP_ORDER[idx + 1] === candidate;
}
