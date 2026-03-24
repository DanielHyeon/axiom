/**
 * BehaviorExecutionPanel — Behavior 실행 & 코드 생성 통합 패널
 *
 * 3개 탭으로 구성된다:
 * 1. 실행 탭: JSON 인스턴스 데이터를 입력하고 Behavior를 실행
 * 2. 코드 생성 탭: 프롬프트로 LLM 코드 생성
 * 3. 결과 저장 탭: 실행 결과를 DB 테이블에 저장
 */

import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Play, Sparkles, Save, Loader2, AlertTriangle, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { useBehaviorExecution } from '../hooks/useBehaviorExecution';
import { CodeViewer } from './CodeViewer';

// ──────────────────────────────────────
// 탭 정의
// ──────────────────────────────────────

type TabKey = 'execute' | 'generate' | 'save';

interface TabDef {
  key: TabKey;
  label: string;
  icon: React.ReactNode;
}

const TABS: (Omit<TabDef, 'label'> & { labelKey: string })[] = [
  { key: 'execute', labelKey: 'behaviorExt.tabs.execute', icon: <Play className="h-3.5 w-3.5" /> },
  { key: 'generate', labelKey: 'behaviorExt.tabs.generate', icon: <Sparkles className="h-3.5 w-3.5" /> },
  { key: 'save', labelKey: 'behaviorExt.tabs.save', icon: <Save className="h-3.5 w-3.5" /> },
];

// ──────────────────────────────────────
// 언어 옵션
// ──────────────────────────────────────

const LANGUAGE_OPTIONS = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'sql', label: 'SQL' },
  { value: 'typescript', label: 'TypeScript' },
];

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface BehaviorExecutionPanelProps {
  /** 실행할 Behavior ID */
  behaviorId?: string;
  /** Behavior 이름 (표시용) */
  behaviorName?: string;
  /** 추가 CSS 클래스 */
  className?: string;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export function BehaviorExecutionPanel({
  behaviorId,
  behaviorName,
  className,
}: BehaviorExecutionPanelProps) {
  const { t } = useTranslation();
  // 탭 상태
  const [activeTab, setActiveTab] = useState<TabKey>('execute');

  // 실행 탭 상태
  const [instanceJson, setInstanceJson] = useState('{\n  \n}');
  const [jsonError, setJsonError] = useState<string | null>(null);

  // 코드 생성 탭 상태
  const [prompt, setPrompt] = useState('');
  const [language, setLanguage] = useState('python');

  // 결과 저장 탭 상태
  const [tableName, setTableName] = useState('');
  const [schemaName, setSchemaName] = useState('');

  // 훅
  const {
    execute,
    generateCode,
    saveResult,
    isExecuting,
    isGenerating,
    isSaving,
    lastResult,
    lastCode,
    lastError,
  } = useBehaviorExecution();

  // ──────────────────────────────────────
  // 핸들러: 실행 탭
  // ──────────────────────────────────────

  /** JSON 유효성을 검증하고 Behavior를 실행한다 */
  const handleExecute = useCallback(async () => {
    if (!behaviorId) return;

    // JSON 파싱 검증
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(instanceJson);
      setJsonError(null);
    } catch {
      setJsonError(t('behaviorExt.invalidJson'));
      return;
    }

    await execute(behaviorId, parsed);
  }, [behaviorId, instanceJson, execute]);

  // ──────────────────────────────────────
  // 핸들러: 코드 생성 탭
  // ──────────────────────────────────────

  /** 프롬프트를 LLM에 전달하여 코드를 생성한다 */
  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return;
    await generateCode(prompt, language);
  }, [prompt, language, generateCode]);

  // ──────────────────────────────────────
  // 핸들러: 결과 저장 탭
  // ──────────────────────────────────────

  /** SQL 식별자 검증 정규식 — injection 방지 */
  const TABLE_NAME_RE = /^[a-zA-Z_][a-zA-Z0-9_]{0,62}$/;

  /** 마지막 실행 결과를 DB에 저장한다 */
  const handleSave = useCallback(async () => {
    if (!tableName.trim() || !lastResult) return;

    // 테이블/스키마 이름 검증 — SQL injection 방지
    if (!TABLE_NAME_RE.test(tableName)) {
      toast.error(t('behaviorExt.tableNameError'));
      return;
    }
    if (schemaName && !TABLE_NAME_RE.test(schemaName)) {
      toast.error(t('behaviorExt.schemaNameError'));
      return;
    }

    // 결과를 배열로 감싼다 (이미 배열이면 그대로)
    const data = Array.isArray(lastResult.result)
      ? (lastResult.result as Record<string, unknown>[])
      : [lastResult.result as Record<string, unknown>];

    await saveResult(tableName, data, schemaName || undefined);
  }, [tableName, schemaName, lastResult, saveResult]);

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Play className="h-4 w-4 text-violet-400" />
          {behaviorName ? `${behaviorName} 실행` : 'Behavior 실행'}
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 탭 네비게이션 */}
        <div className="flex gap-1 p-1 rounded-lg bg-muted" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                activeTab === tab.key
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {tab.icon}
              {t(tab.labelKey)}
            </button>
          ))}
        </div>

        {/* 에러 표시 */}
        {lastError && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {lastError}
          </div>
        )}

        {/* ── 실행 탭 ── */}
        {activeTab === 'execute' && (
          <div className="space-y-3">
            {/* Behavior ID 표시 */}
            {behaviorId && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Behavior ID:</span>
                <Badge variant="outline" className="font-mono text-xs">
                  {behaviorId}
                </Badge>
              </div>
            )}

            {/* JSON 입력 영역 */}
            <div className="space-y-1">
              <label
                htmlFor="instance-data"
                className="text-sm font-medium text-foreground"
              >
                {t('behaviorExt.instanceDataLabel')}
              </label>
              <Textarea
                id="instance-data"
                value={instanceJson}
                onChange={(e) => {
                  setInstanceJson(e.target.value);
                  setJsonError(null);
                }}
                placeholder='{ "key": "value" }'
                className="font-mono text-sm min-h-[160px] resize-y"
              />
              {jsonError && (
                <p className="text-xs text-destructive">{jsonError}</p>
              )}
            </div>

            {/* 실행 버튼 */}
            <Button
              onClick={handleExecute}
              disabled={!behaviorId || isExecuting}
              className="w-full"
            >
              {isExecuting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('behaviorExt.executing')}
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  {t('behaviorExt.executeBtn')}
                </>
              )}
            </Button>

            {/* 실행 결과 표시 */}
            {lastResult && (
              <div className="space-y-2">
                {/* 자동 수정 알림 */}
                {lastResult.autoFixed && (
                  <div className="flex items-center gap-2 p-2 rounded-md bg-amber-500/10 text-amber-500 text-xs">
                    <Wrench className="h-3.5 w-3.5 shrink-0" />
                    {t('behaviorExt.autoFixNotice', { count: lastResult.attempts ?? 1 })}
                  </div>
                )}

                {/* 결과 상태 */}
                <div className="flex items-center gap-2 text-sm">
                  <Badge
                    variant={lastResult.success ? 'default' : 'destructive'}
                    className="text-xs"
                  >
                    {lastResult.success ? '성공' : '실패'}
                  </Badge>
                  <span className="text-muted-foreground">
                    {lastResult.message}
                  </span>
                </div>

                {/* 결과 데이터 */}
                <CodeViewer
                  code={JSON.stringify(lastResult.result, null, 2)}
                  language="json"
                />

                {/* 자동 수정된 코드 표시 */}
                {lastResult.code && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      {t('behaviorExt.executedCode')}
                    </p>
                    <CodeViewer code={lastResult.code} language="python" />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── 코드 생성 탭 ── */}
        {activeTab === 'generate' && (
          <div className="space-y-3">
            {/* 프롬프트 입력 */}
            <div className="space-y-1">
              <label
                htmlFor="code-prompt"
                className="text-sm font-medium text-foreground"
              >
                {t('behaviorExt.promptLabel')}
              </label>
              <Textarea
                id="code-prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={t('behaviorExt.promptPlaceholder')}
                className="min-h-[120px] resize-y"
              />
            </div>

            {/* 언어 선택 */}
            <div className="space-y-1">
              <label
                htmlFor="code-language"
                className="text-sm font-medium text-foreground"
              >
                {t('behaviorExt.languageLabel')}
              </label>
              <select
                id="code-language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {LANGUAGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* 생성 버튼 */}
            <Button
              onClick={handleGenerate}
              disabled={!prompt.trim() || isGenerating}
              className="w-full"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('behaviorExt.generating')}
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  {t('behaviorExt.generateBtn')}
                </>
              )}
            </Button>

            {/* 생성된 코드 표시 */}
            {lastCode && (
              <CodeViewer code={lastCode.code} language={lastCode.language} />
            )}
          </div>
        )}

        {/* ── 결과 저장 탭 ── */}
        {activeTab === 'save' && (
          <div className="space-y-3">
            {/* 저장 가능 여부 확인 */}
            {!lastResult ? (
              <div className="text-sm text-muted-foreground text-center py-6 border border-dashed border-border rounded-lg">
                {t('behaviorExt.saveRunFirst')}
              </div>
            ) : (
              <>
                {/* 테이블 이름 */}
                <div className="space-y-1">
                  <label
                    htmlFor="table-name"
                    className="text-sm font-medium text-foreground"
                  >
                    {t('behaviorExt.tableNameLabel')}
                  </label>
                  <Input
                    id="table-name"
                    value={tableName}
                    onChange={(e) => setTableName(e.target.value)}
                    placeholder={t('behaviorExt.tableExample')}
                    className="font-mono"
                  />
                </div>

                {/* 스키마 이름 (선택) */}
                <div className="space-y-1">
                  <label
                    htmlFor="schema-name"
                    className="text-sm font-medium text-foreground"
                  >
                    {t('behaviorExt.schemaNameLabel')}
                  </label>
                  <Input
                    id="schema-name"
                    value={schemaName}
                    onChange={(e) => setSchemaName(e.target.value)}
                    placeholder={t('behaviorExt.schemaExample')}
                    className="font-mono"
                  />
                </div>

                {/* 데이터 프리뷰 */}
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">
                    {t('behaviorExt.dataPreview')}
                  </p>
                  <CodeViewer
                    code={JSON.stringify(lastResult.result, null, 2)}
                    language="json"
                    className="max-h-[200px] overflow-y-auto"
                  />
                </div>

                {/* 저장 버튼 */}
                <Button
                  onClick={handleSave}
                  disabled={!tableName.trim() || isSaving}
                  className="w-full"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {t('behaviorExt.saving')}
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      {t('behaviorExt.saveBtn')}
                    </>
                  )}
                </Button>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
