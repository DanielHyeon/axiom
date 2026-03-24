/**
 * CEPRulesPage — CEP 규칙 관리 페이지
 *
 * 기능:
 * - 규칙 목록 테이블 (이름, 조건, 임계값, 심각도, 활성/비활성, 액션)
 * - 새 규칙 생성 / 수정 모달
 * - 규칙 수동 평가 (값 입력 → 결과 표시)
 * - 평가 이력 조회
 */
import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Plus,
  Pencil,
  Trash2,
  Play,
  History,
  X,
  AlertTriangle,
  AlertCircle,
  Info,
  Loader2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from '@/components/ui/select';

import * as api from '../api/cepApi';
import type {
  CEPRule,
  CEPRulePayload,
  CEPResult,
  CEPHistoryItem,
  ConditionType,
  Severity,
} from '../types/cep';

// ─── 상수 ──────────────────────────────────────────────────

/** 조건 유형 키 매핑 — t()로 라벨 조회 */
const CONDITION_KEYS: ConditionType[] = [
  'greater_than', 'less_than', 'equal', 'not_equal',
  'greater_equal', 'less_equal', 'between', 'contains',
];

/** 심각도 색상 매핑 */
const SEVERITY_VARIANT: Record<Severity, 'destructive' | 'default' | 'secondary'> = {
  critical: 'destructive',
  warning: 'default',
  info: 'secondary',
};

/** 심각도 아이콘 */
const SeverityIcon = ({ severity }: { severity: Severity }) => {
  if (severity === 'critical') return <AlertCircle className="h-3.5 w-3.5" />;
  if (severity === 'warning') return <AlertTriangle className="h-3.5 w-3.5" />;
  return <Info className="h-3.5 w-3.5" />;
};

/** 빈 규칙 폼 초기값 */
const EMPTY_FORM: CEPRulePayload = {
  name: '',
  sql_query: '',
  condition_type: 'greater_than',
  threshold: 0,
  severity: 'warning',
  enabled: true,
};

// ─── 메인 컴포넌트 ──────────────────────────────────────────

export function CEPRulesPage() {
  const { t } = useTranslation();
  // 규칙 목록 상태
  const [rules, setRules] = useState<CEPRule[]>([]);
  const [loading, setLoading] = useState(true);

  // 모달 상태 — 생성/수정 폼
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<CEPRulePayload>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);

  // 수동 평가 상태
  const [evalRuleId, setEvalRuleId] = useState<string | null>(null);
  const [evalValue, setEvalValue] = useState('');
  const [evalResult, setEvalResult] = useState<CEPResult | null>(null);
  const [evaluating, setEvaluating] = useState(false);

  // 이력 조회 상태
  const [historyRuleId, setHistoryRuleId] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<CEPHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // ─── 데이터 로드 ───────────────────────────────────────────

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listRules();
      setRules(data);
    } catch (err) {
      toast.error(t('cepExt.toast.fetchFailed'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  // ─── 모달 열기/닫기 ────────────────────────────────────────

  const openCreateModal = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setModalOpen(true);
  };

  const openEditModal = (rule: CEPRule) => {
    setEditingId(rule.id);
    setForm({
      name: rule.name,
      description: rule.description,
      sql_query: rule.sql_query,
      condition_type: rule.condition_type,
      threshold: rule.threshold,
      threshold_upper: rule.threshold_upper,
      severity: rule.severity,
      enabled: rule.enabled,
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
  };

  // ─── 저장 (생성/수정) ─────────────────────────────────────

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error(t('cepExt.toast.nameRequired'));
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await api.updateRule(editingId, form);
        toast.success(t('cepExt.toast.updated'));
      } else {
        await api.createRule(form);
        toast.success(t('cepExt.toast.created'));
      }
      closeModal();
      fetchRules();
    } catch {
      toast.error(editingId ? t('cepExt.toast.updateFailed') : t('cepExt.toast.createFailed'));
    } finally {
      setSaving(false);
    }
  };

  // ─── 삭제 ─────────────────────────────────────────────────

  const handleDelete = async (id: string) => {
    if (!window.confirm(t('cepExt.toast.deleteConfirm'))) return;
    try {
      await api.deleteRule(id);
      toast.success(t('cepExt.toast.deleted'));
      fetchRules();
    } catch {
      toast.error(t('cepExt.toast.deleteFailed'));
    }
  };

  // ─── 활성/비활성 토글 ──────────────────────────────────────

  const handleToggleEnabled = async (rule: CEPRule) => {
    try {
      await api.updateRule(rule.id, { enabled: !rule.enabled });
      // 로컬 상태 즉시 반영 — 깜빡임 방지
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, enabled: !r.enabled } : r)),
      );
    } catch {
      toast.error(t('cepExt.toast.toggleFailed'));
    }
  };

  // ─── 수동 평가 ────────────────────────────────────────────

  const handleEvaluate = async () => {
    if (!evalRuleId) return;
    const numVal = parseFloat(evalValue);
    if (isNaN(numVal)) {
      toast.error(t('cepExt.toast.numberRequired'));
      return;
    }
    setEvaluating(true);
    try {
      const result = await api.evaluateRule(evalRuleId, numVal);
      setEvalResult(result);
    } catch {
      toast.error(t('cepExt.toast.evalFailed'));
    } finally {
      setEvaluating(false);
    }
  };

  // ─── 이력 조회 ────────────────────────────────────────────

  const handleShowHistory = async (ruleId: string) => {
    setHistoryRuleId(ruleId);
    setHistoryLoading(true);
    try {
      const items = await api.getRuleHistory(ruleId);
      setHistoryItems(items);
    } catch {
      toast.error(t('cepExt.toast.historyFailed'));
    } finally {
      setHistoryLoading(false);
    }
  };

  // ─── 렌더링 ───────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-6 p-6 max-w-[1200px] mx-auto">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{t('cepExt.title')}</h1>
          <p className="text-sm text-foreground/50 mt-1">
            {t('cepExt.subtitle')}
          </p>
        </div>
        <Button onClick={openCreateModal} className="gap-1.5">
          <Plus className="h-4 w-4" />
          {t('cepExt.newRule')}
        </Button>
      </div>

      {/* 규칙 테이블 */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-foreground/30" />
        </div>
      ) : rules.length === 0 ? (
        <div className="text-center py-16 text-sm text-foreground/40">
          {t('cepExt.noRules')}
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('cepExt.colName')}</TableHead>
              <TableHead>{t('cepExt.colCondition')}</TableHead>
              <TableHead>{t('cepExt.colThreshold')}</TableHead>
              <TableHead>{t('cepExt.colSeverity')}</TableHead>
              <TableHead>{t('cepExt.colEnabled')}</TableHead>
              <TableHead className="text-right">{t('cepExt.colActions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((rule) => (
              <TableRow key={rule.id}>
                {/* 이름 */}
                <TableCell className="font-medium">{rule.name}</TableCell>

                {/* 조건 */}
                <TableCell className="text-foreground/60 text-xs font-mono">
                  {t(`cepExt.conditionLabels.${rule.condition_type}`, rule.condition_type)}
                </TableCell>

                {/* 임계값 */}
                <TableCell className="font-mono text-xs">
                  {rule.condition_type === 'between'
                    ? `${rule.threshold} ~ ${rule.threshold_upper ?? '?'}`
                    : rule.threshold}
                </TableCell>

                {/* 심각도 뱃지 */}
                <TableCell>
                  <Badge variant={SEVERITY_VARIANT[rule.severity]} className="gap-1">
                    <SeverityIcon severity={rule.severity} />
                    {rule.severity}
                  </Badge>
                </TableCell>

                {/* 활성 토글 — 네이티브 체크박스 + 토글 스타일 */}
                <TableCell>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={rule.enabled}
                    onClick={() => handleToggleEnabled(rule)}
                    className={`
                      relative inline-flex h-5 w-9 items-center rounded-full transition-colors
                      ${rule.enabled ? 'bg-blue-500' : 'bg-foreground/20'}
                    `}
                  >
                    <span
                      className={`
                        inline-block h-3.5 w-3.5 rounded-full bg-card transition-transform
                        ${rule.enabled ? 'translate-x-4.5' : 'translate-x-0.5'}
                      `}
                    />
                  </button>
                </TableCell>

                {/* 액션 버튼 */}
                <TableCell>
                  <div className="flex items-center justify-end gap-1">
                    {/* 수동 평가 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      title={t('cepExt.manualEval')}
                      onClick={() => {
                        setEvalRuleId(rule.id);
                        setEvalValue('');
                        setEvalResult(null);
                      }}
                    >
                      <Play className="h-3.5 w-3.5" />
                    </Button>

                    {/* 이력 조회 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      title={t('cepExt.evalHistory')}
                      onClick={() => handleShowHistory(rule.id)}
                    >
                      <History className="h-3.5 w-3.5" />
                    </Button>

                    {/* 수정 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      title={t('common.edit')}
                      onClick={() => openEditModal(rule)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>

                    {/* 삭제 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-red-500 hover:text-red-600"
                      title={t('common.delete')}
                      onClick={() => handleDelete(rule.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ─── 생성/수정 모달 ────────────────────────────────── */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => e.target === e.currentTarget && closeModal()}
        >
          <div className="bg-card rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <h2 className="text-base font-semibold">
                {editingId ? t('cepExt.editRule') : t('cepExt.createRule')}
              </h2>
              <button onClick={closeModal} className="text-foreground/40 hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* 폼 본문 */}
            <div className="flex flex-col gap-4 px-6 py-5">
              {/* 이름 */}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground/70">{t('cepExt.ruleName')}</label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder={t('cepExt.ruleNamePlaceholder')}
                />
              </div>

              {/* 설명 */}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground/70">{t('cepExt.descriptionOpt')}</label>
                <Input
                  value={form.description ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder={t('cepExt.descriptionPlaceholder')}
                />
              </div>

              {/* SQL 쿼리 */}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground/70">{t('cepExt.sqlQuery')}</label>
                <Textarea
                  value={form.sql_query}
                  onChange={(e) => setForm((f) => ({ ...f, sql_query: e.target.value }))}
                  placeholder="SELECT count(*) FROM inventory WHERE quantity < 10"
                  rows={3}
                  className="font-mono text-xs"
                />
              </div>

              {/* 조건 유형 + 임계값 */}
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-foreground/70">{t('cepExt.conditionType')}</label>
                  <Select
                    value={form.condition_type}
                    onValueChange={(v) =>
                      setForm((f) => ({ ...f, condition_type: v as ConditionType }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CONDITION_KEYS.map((key) => (
                          <SelectItem key={key} value={key}>
                            {t(`cepExt.conditionLabels.${key}`)}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-foreground/70">{t('cepExt.threshold')}</label>
                  <Input
                    type="number"
                    value={form.threshold}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, threshold: parseFloat(e.target.value) || 0 }))
                    }
                  />
                </div>
              </div>

              {/* between일 때 상한값 */}
              {form.condition_type === 'between' && (
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-foreground/70">{t('cepExt.thresholdUpper')}</label>
                  <Input
                    type="number"
                    value={form.threshold_upper ?? ''}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        threshold_upper: parseFloat(e.target.value) || 0,
                      }))
                    }
                  />
                </div>
              )}

              {/* 심각도 */}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground/70">{t('cepExt.severity')}</label>
                <Select
                  value={form.severity}
                  onValueChange={(v) => setForm((f) => ({ ...f, severity: v as Severity }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">Critical</SelectItem>
                    <SelectItem value="warning">Warning</SelectItem>
                    <SelectItem value="info">Info</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border">
              <Button variant="outline" onClick={closeModal} disabled={saving}>
                {t('common.cancel')}
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin mr-1.5" />}
                {editingId ? t('common.edit') : t('common.confirm')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ─── 수동 평가 패널 ───────────────────────────────── */}
      {evalRuleId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => e.target === e.currentTarget && setEvalRuleId(null)}
        >
          <div className="bg-card rounded-lg shadow-xl w-full max-w-sm mx-4">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border">
              <h3 className="text-sm font-semibold">{t('cepExt.manualEval')}</h3>
              <button
                onClick={() => setEvalRuleId(null)}
                className="text-foreground/40 hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3 px-5 py-4">
              <div className="flex gap-2">
                <Input
                  type="number"
                  value={evalValue}
                  onChange={(e) => setEvalValue(e.target.value)}
                  placeholder={t('cepExt.evalValuePlaceholder')}
                  className="flex-1"
                />
                <Button onClick={handleEvaluate} disabled={evaluating} size="sm">
                  {evaluating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {/* 평가 결과 표시 */}
              {evalResult && (
                <div
                  className={`
                    rounded-md px-3 py-2 text-xs
                    ${evalResult.triggered ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}
                  `}
                >
                  <div className="font-semibold mb-1">
                    {evalResult.triggered ? t('cepExt.triggered') : t('cepExt.notTriggered')}
                  </div>
                  <div>{t('cepExt.evalValue', { value: evalResult.evaluated_value })}</div>
                  {evalResult.message && <div className="mt-1">{evalResult.message}</div>}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── 이력 패널 ───────────────────────────────────── */}
      {historyRuleId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => e.target === e.currentTarget && setHistoryRuleId(null)}
        >
          <div className="bg-card rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[70vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
              <h3 className="text-sm font-semibold">{t('cepExt.evalHistory')}</h3>
              <button
                onClick={() => setHistoryRuleId(null)}
                className="text-foreground/40 hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {historyLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-foreground/30" />
                </div>
              ) : historyItems.length === 0 ? (
                <p className="text-center text-sm text-foreground/40 py-8">
                  {t('cepExt.noHistory')}
                </p>
              ) : (
                <div className="flex flex-col gap-2">
                  {historyItems.map((item) => (
                    <div
                      key={item.id}
                      className={`
                        flex items-center justify-between rounded-md px-3 py-2 text-xs border
                        ${item.triggered ? 'border-red-200 bg-red-50/50' : 'border-border bg-muted/50'}
                      `}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-2 w-2 rounded-full ${item.triggered ? 'bg-red-500' : 'bg-green-500'}`}
                        />
                        <span className="font-mono">{item.evaluated_value}</span>
                      </div>
                      <span className="text-foreground/40">
                        {new Date(item.evaluated_at).toLocaleString('ko-KR')}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
