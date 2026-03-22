/**
 * 규칙/정책 패널 — 온톨로지 규칙 + 정책을 2섹션으로 관리
 *
 * 규칙 섹션: 접이식 생성 폼 + 테이블 (rule_type 배지, severity 배지)
 * 정책 섹션: 접이식 생성 폼 + 테이블 (policy_type 배지, is_active 토글)
 */
import { useState } from 'react';
import { Scale, Shield, Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import type {
  OntologyRule,
  OntologyPolicy,
  RuleType,
  PolicyType,
} from '../types/semantic';

// ── 규칙 타입 배지 색상 ──
const RULE_TYPE_COLORS: Record<RuleType, string> = {
  definition: 'bg-blue-50 text-blue-700',
  eligibility: 'bg-emerald-50 text-emerald-700',
  exclusion: 'bg-red-50 text-red-700',
  time_window: 'bg-amber-50 text-amber-700',
  policy: 'bg-violet-50 text-violet-700',
};

// ── 심각도 배지 색상 ──
const SEVERITY_COLORS: Record<string, string> = {
  error: 'bg-red-100 text-red-800',
  warning: 'bg-yellow-100 text-yellow-800',
  info: 'bg-blue-100 text-blue-800',
  critical: 'bg-red-200 text-red-900',
};

// ── 정책 타입 배지 색상 ──
const POLICY_TYPE_COLORS: Record<PolicyType, string> = {
  access: 'bg-indigo-50 text-indigo-700',
  pii: 'bg-red-50 text-red-700',
  retention: 'bg-amber-50 text-amber-700',
  residency: 'bg-cyan-50 text-cyan-700',
  aggregation: 'bg-emerald-50 text-emerald-700',
};

const RULE_TYPE_OPTIONS: RuleType[] = ['definition', 'eligibility', 'exclusion', 'time_window', 'policy'];
const POLICY_TYPE_OPTIONS: PolicyType[] = ['access', 'pii', 'retention', 'residency', 'aggregation'];
const EXPRESSION_LANG_OPTIONS = ['python', 'sql', 'jexl', 'cel'];
const SEVERITY_OPTIONS = ['info', 'warning', 'error', 'critical'];

interface Props {
  rules: OntologyRule[];
  policies: OntologyPolicy[];
  onCreateRule?: (data: Partial<OntologyRule>) => void;
  onDeleteRule?: (ruleId: string) => void;
  onCreatePolicy?: (data: Partial<OntologyPolicy>) => void;
  onDeletePolicy?: (policyId: string) => void;
  onTogglePolicyActive?: (policyId: string, isActive: boolean) => void;
  isCreatingRule?: boolean;
  isCreatingPolicy?: boolean;
}

/** 규칙 생성 폼 초기값 */
const EMPTY_RULE = {
  concept_id: '',
  rule_type: 'definition' as RuleType,
  rule_expression: '',
  expression_lang: 'python',
  severity: 'warning',
  description: '',
};

/** 정책 생성 폼 초기값 */
const EMPTY_POLICY = {
  concept_id: '',
  policy_type: 'access' as PolicyType,
  policy_expression: '',
  description: '',
};

export function RulePolicyPanel({
  rules,
  policies,
  onCreateRule,
  onDeleteRule,
  onCreatePolicy,
  onDeletePolicy,
  onTogglePolicyActive,
  isCreatingRule,
  isCreatingPolicy,
}: Props) {
  // ── 규칙 폼 상태 ──
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleForm, setRuleForm] = useState({ ...EMPTY_RULE });

  // ── 정책 폼 상태 ──
  const [showPolicyForm, setShowPolicyForm] = useState(false);
  const [policyForm, setPolicyForm] = useState({ ...EMPTY_POLICY });

  const handleRuleChange = (field: string, value: string) =>
    setRuleForm((prev) => ({ ...prev, [field]: value }));

  const handlePolicyChange = (field: string, value: string) =>
    setPolicyForm((prev) => ({ ...prev, [field]: value }));

  const handleRuleSubmit = () => {
    if (!ruleForm.concept_id || !ruleForm.rule_expression) return;
    onCreateRule?.({
      ...ruleForm,
      description: ruleForm.description || undefined,
    });
    setRuleForm({ ...EMPTY_RULE });
    setShowRuleForm(false);
  };

  const handlePolicySubmit = () => {
    if (!policyForm.concept_id || !policyForm.policy_expression) return;
    onCreatePolicy?.({
      ...policyForm,
      description: policyForm.description || undefined,
    });
    setPolicyForm({ ...EMPTY_POLICY });
    setShowPolicyForm(false);
  };

  return (
    <div className="space-y-6">
      {/* ═══════ 규칙 섹션 ═══════ */}
      <div className="rounded-lg border">
        {/* 규칙 헤더 */}
        <div className="flex items-center justify-between border-b bg-muted/50 px-3 py-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Scale className="h-4 w-4 text-blue-600" />
            온톨로지 규칙
          </div>
          {onCreateRule && (
            <button
              className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
              onClick={() => setShowRuleForm(!showRuleForm)}
            >
              {showRuleForm ? <ChevronUp className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
              {showRuleForm ? '닫기' : '규칙 등록'}
            </button>
          )}
        </div>

        {/* 규칙 생성 폼 */}
        {showRuleForm && (
          <div className="border-b bg-muted/20 px-4 py-3 space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">개념 ID</label>
                <input
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  placeholder="concept_..."
                  value={ruleForm.concept_id}
                  onChange={(e) => handleRuleChange('concept_id', e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">규칙 타입</label>
                <select
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  value={ruleForm.rule_type}
                  onChange={(e) => handleRuleChange('rule_type', e.target.value)}
                >
                  {RULE_TYPE_OPTIONS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">언어</label>
                <select
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  value={ruleForm.expression_lang}
                  onChange={(e) => handleRuleChange('expression_lang', e.target.value)}
                >
                  {EXPRESSION_LANG_OPTIONS.map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">심각도</label>
                <select
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  value={ruleForm.severity}
                  onChange={(e) => handleRuleChange('severity', e.target.value)}
                >
                  {SEVERITY_OPTIONS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">표현식</label>
              <textarea
                className="w-full rounded-md border px-2 py-1.5 text-sm font-mono h-16 resize-y"
                placeholder="규칙 표현식을 입력하세요..."
                value={ruleForm.rule_expression}
                onChange={(e) => handleRuleChange('rule_expression', e.target.value)}
              />
            </div>
            <div className="flex items-center gap-3">
              <input
                className="flex-1 rounded-md border px-2 py-1.5 text-sm"
                placeholder="설명 (선택)"
                value={ruleForm.description}
                onChange={(e) => handleRuleChange('description', e.target.value)}
              />
              <button
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                disabled={isCreatingRule || !ruleForm.concept_id || !ruleForm.rule_expression}
                onClick={handleRuleSubmit}
              >
                {isCreatingRule ? '등록 중...' : '등록'}
              </button>
            </div>
          </div>
        )}

        {/* 규칙 테이블 */}
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2 text-left font-medium">규칙 ID</th>
              <th className="px-3 py-2 text-left font-medium">개념 ID</th>
              <th className="px-3 py-2 text-left font-medium">타입</th>
              <th className="px-3 py-2 text-left font-medium">표현식</th>
              <th className="px-3 py-2 text-center font-medium">심각도</th>
              <th className="px-3 py-2 text-center font-medium">언어</th>
              {onDeleteRule && <th className="px-3 py-2 w-10" />}
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => {
              const typeBadge = RULE_TYPE_COLORS[r.rule_type as RuleType] ?? 'bg-slate-100 text-slate-700';
              const sevBadge = SEVERITY_COLORS[r.severity] ?? SEVERITY_COLORS.info;
              return (
                <tr key={r.rule_id} className="border-b hover:bg-muted/30">
                  <td className="px-3 py-2 font-mono text-xs">{r.rule_id}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{r.concept_id}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${typeBadge}`}>
                      {r.rule_type}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground max-w-[300px] truncate" title={r.rule_expression}>
                    {r.rule_expression}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${sevBadge}`}>
                      {r.severity}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-center text-xs text-muted-foreground">{r.expression_lang}</td>
                  {onDeleteRule && (
                    <td className="px-3 py-2">
                      <button
                        className="p-1 rounded hover:bg-red-50 text-red-500 hover:text-red-700"
                        title="삭제"
                        onClick={() => onDeleteRule(r.rule_id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {rules.length === 0 && (
          <div className="py-8 text-center text-muted-foreground text-sm">등록된 규칙이 없습니다</div>
        )}
      </div>

      {/* ═══════ 정책 섹션 ═══════ */}
      <div className="rounded-lg border">
        {/* 정책 헤더 */}
        <div className="flex items-center justify-between border-b bg-muted/50 px-3 py-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Shield className="h-4 w-4 text-indigo-600" />
            온톨로지 정책
          </div>
          {onCreatePolicy && (
            <button
              className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
              onClick={() => setShowPolicyForm(!showPolicyForm)}
            >
              {showPolicyForm ? <ChevronUp className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
              {showPolicyForm ? '닫기' : '정책 등록'}
            </button>
          )}
        </div>

        {/* 정책 생성 폼 */}
        {showPolicyForm && (
          <div className="border-b bg-muted/20 px-4 py-3 space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">개념 ID</label>
                <input
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  placeholder="concept_..."
                  value={policyForm.concept_id}
                  onChange={(e) => handlePolicyChange('concept_id', e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">정책 타입</label>
                <select
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  value={policyForm.policy_type}
                  onChange={(e) => handlePolicyChange('policy_type', e.target.value)}
                >
                  {POLICY_TYPE_OPTIONS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">설명 (선택)</label>
                <input
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  placeholder="정책 설명..."
                  value={policyForm.description}
                  onChange={(e) => handlePolicyChange('description', e.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">정책 표현식</label>
              <textarea
                className="w-full rounded-md border px-2 py-1.5 text-sm font-mono h-16 resize-y"
                placeholder="정책 표현식을 입력하세요..."
                value={policyForm.policy_expression}
                onChange={(e) => handlePolicyChange('policy_expression', e.target.value)}
              />
            </div>
            <button
              className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              disabled={isCreatingPolicy || !policyForm.concept_id || !policyForm.policy_expression}
              onClick={handlePolicySubmit}
            >
              {isCreatingPolicy ? '등록 중...' : '등록'}
            </button>
          </div>
        )}

        {/* 정책 테이블 */}
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2 text-left font-medium">정책 ID</th>
              <th className="px-3 py-2 text-left font-medium">개념 ID</th>
              <th className="px-3 py-2 text-left font-medium">타입</th>
              <th className="px-3 py-2 text-left font-medium">표현식</th>
              <th className="px-3 py-2 text-center font-medium">활성</th>
              {onDeletePolicy && <th className="px-3 py-2 w-10" />}
            </tr>
          </thead>
          <tbody>
            {policies.map((p) => {
              const typeBadge = POLICY_TYPE_COLORS[p.policy_type as PolicyType] ?? 'bg-slate-100 text-slate-700';
              return (
                <tr key={p.policy_id} className="border-b hover:bg-muted/30">
                  <td className="px-3 py-2 font-mono text-xs">{p.policy_id}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{p.concept_id}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${typeBadge}`}>
                      {p.policy_type}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground max-w-[300px] truncate" title={p.policy_expression}>
                    {p.policy_expression}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {/* 활성/비활성 토글 */}
                    <button
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${p.is_active ? 'bg-green-500' : 'bg-gray-300'}`}
                      onClick={() => onTogglePolicyActive?.(p.policy_id, !p.is_active)}
                      title={p.is_active ? '비활성화' : '활성화'}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${p.is_active ? 'translate-x-4.5' : 'translate-x-0.5'}`}
                      />
                    </button>
                  </td>
                  {onDeletePolicy && (
                    <td className="px-3 py-2">
                      <button
                        className="p-1 rounded hover:bg-red-50 text-red-500 hover:text-red-700"
                        title="삭제"
                        onClick={() => onDeletePolicy(p.policy_id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {policies.length === 0 && (
          <div className="py-8 text-center text-muted-foreground text-sm">등록된 정책이 없습니다</div>
        )}
      </div>
    </div>
  );
}
