/**
 * DMN 결정 테이블 그리드 에디터.
 * KG-1: 조건(input) 컬럼 + 결과(output) 컬럼 + 규칙 행 편집.
 *
 * KAIR DmnEditor.vue 이식 — React + Tailwind 기반.
 */

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Plus, Trash2, Play } from 'lucide-react';
import { HitPolicySelector } from './HitPolicySelector';
import type { DecisionTable, DmnColumn, DmnRule, HitPolicy, DmnTestRequest } from '../types/dmn';
import { useTranslation } from 'react-i18next';

interface DmnTableEditorProps {
  table: DecisionTable;
  onSave: (updates: Partial<Pick<DecisionTable, 'hitPolicy' | 'columns' | 'rules'>>) => void;
  onTest: (request: DmnTestRequest) => void;
  testResult?: { matchedRules: string[]; outputs: Record<string, unknown> } | null;
  isSaving?: boolean;
}

export function DmnTableEditor({ table, onSave, onTest, testResult, isSaving }: DmnTableEditorProps) {
  const { t } = useTranslation();
  const [hitPolicy, setHitPolicy] = useState<HitPolicy>(table.hitPolicy);
  const [columns, _setColumns] = useState<DmnColumn[]>(table.columns);
  const [rules, setRules] = useState<DmnRule[]>(table.rules);
  const [testInputs, setTestInputs] = useState<Record<string, string>>({});

  const inputCols = columns.filter((c) => c.kind === 'input');
  const outputCols = columns.filter((c) => c.kind === 'output');

  // 셀 값 변경
  const updateCell = useCallback((ruleId: string, colId: string, value: string) => {
    setRules((prev) =>
      prev.map((r) =>
        r.id === ruleId ? { ...r, cells: { ...r.cells, [colId]: value } } : r
      )
    );
  }, []);

  // 규칙 추가
  const addRule = useCallback(() => {
    const newRule: DmnRule = {
      id: `rule-${Date.now()}`,
      priority: rules.length + 1,
      cells: Object.fromEntries(columns.map((c) => [c.id, ''])),
    };
    setRules((prev) => [...prev, newRule]);
  }, [columns, rules.length]);

  // 규칙 삭제
  const removeRule = useCallback((ruleId: string) => {
    setRules((prev) => prev.filter((r) => r.id !== ruleId));
  }, []);

  // 저장
  const handleSave = () => {
    onSave({ hitPolicy, columns, rules });
  };

  // 테스트 실행
  const handleTest = () => {
    const inputs: Record<string, unknown> = {};
    for (const col of inputCols) {
      const raw = testInputs[col.id] ?? '';
      inputs[col.name] = col.dataType === 'number' ? Number(raw) : col.dataType === 'boolean' ? raw === 'true' : raw;
    }
    onTest({ inputs });
  };

  return (
    <div className="space-y-4">
      {/* 헤더: 이름 + 적중 정책 + 저장 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">{table.name}</h2>
          {table.description && <p className="text-sm text-muted-foreground">{table.description}</p>}
        </div>
        <div className="flex items-center gap-3">
          <HitPolicySelector value={hitPolicy} onChange={setHitPolicy} />
          <Button onClick={handleSave} disabled={isSaving} size="sm">
            {isSaving ? '저장 중...' : '저장'}
          </Button>
        </div>
      </div>

      {/* 결정 테이블 그리드 */}
      <div className="border border-border rounded-lg overflow-auto">
        <table className="w-full text-sm">
          <thead>
            {/* 그룹 헤더: 조건 | 결과 */}
            <tr className="border-b border-border">
              <th className="w-10 bg-muted" />
              {inputCols.length > 0 && (
                <th
                  colSpan={inputCols.length}
                  className="px-3 py-1.5 text-center text-xs font-medium text-primary bg-primary/5 border-r border-border"
                >
                  {t('dmn.inputHeader')}
                </th>
              )}
              {outputCols.length > 0 && (
                <th
                  colSpan={outputCols.length}
                  className="px-3 py-1.5 text-center text-xs font-medium text-success bg-success/5"
                >
                  {t('dmn.outputHeader')}
                </th>
              )}
              <th className="w-10 bg-muted" />
            </tr>
            {/* 컬럼 이름 헤더 */}
            <tr className="border-b border-border bg-muted/50">
              <th className="w-10 px-2 text-xs text-muted-foreground">#</th>
              {columns.map((col) => (
                <th
                  key={col.id}
                  className={`px-3 py-2 text-left text-xs font-medium ${
                    col.kind === 'input' ? 'text-primary' : 'text-success'
                  }`}
                >
                  <div>{col.name}</div>
                  <div className="text-[10px] text-muted-foreground font-normal">{col.dataType}</div>
                </th>
              ))}
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {rules.map((rule, idx) => (
              <tr
                key={rule.id}
                className={`border-b border-border hover:bg-muted/30 ${
                  testResult?.matchedRules.includes(rule.id) ? 'bg-success/10' : ''
                }`}
              >
                <td className="px-2 text-xs text-muted-foreground text-center">{idx + 1}</td>
                {columns.map((col) => (
                  <td key={col.id} className="px-1 py-1">
                    <Input
                      value={rule.cells[col.id] ?? ''}
                      onChange={(e) => updateCell(rule.id, col.id, e.target.value)}
                      className="h-7 text-xs border-0 bg-transparent focus:bg-card"
                      placeholder={col.kind === 'input' ? '조건...' : '결과...'}
                    />
                  </td>
                ))}
                <td className="px-1">
                  <button
                    type="button"
                    onClick={() => removeRule(rule.id)}
                    className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                    aria-label={`규칙 ${idx + 1} 삭제`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 규칙 추가 버튼 */}
      <Button variant="outline" size="sm" onClick={addRule} className="gap-1">
        <Plus className="h-3.5 w-3.5" /> {t('dmn.addRule')}
      </Button>

      {/* 테스트 실행 패널 */}
      <div className="border border-border rounded-lg p-4 bg-card">
        <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
          <Play className="h-4 w-4" /> {t('dmn.testRun')}
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {inputCols.map((col) => (
            <div key={col.id}>
              <label className="text-xs text-muted-foreground">{col.name}</label>
              <Input
                value={testInputs[col.id] ?? ''}
                onChange={(e) => setTestInputs((prev) => ({ ...prev, [col.id]: e.target.value }))}
                className="h-8 text-sm mt-1"
                placeholder={col.dataType}
              />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3 mt-3">
          <Button size="sm" onClick={handleTest} className="gap-1">
            <Play className="h-3.5 w-3.5" /> {t('common.run')}
          </Button>
          {testResult && (
            <div className="text-sm">
              <span className="text-muted-foreground">{t('dmn.matchCount')}: </span>
              <span className="font-medium">{testResult.matchedRules.length}{t('dmn.matchUnit')}</span>
              {Object.entries(testResult.outputs).map(([k, v]) => (
                <span key={k} className="ml-3">
                  <span className="text-muted-foreground">{k}: </span>
                  <span className="font-mono text-success">{String(v)}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
