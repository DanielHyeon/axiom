/**
 * IncidentDetail — 인시던트 상세 패널 (Sheet / Slide-over)
 * 선택된 DQ 규칙의 상세 정보, 최근 실행 결과, 인시던트 히스토리를 표시합니다.
 */
import { X, Play, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { useDQStore } from '../store/useDQStore';
import { useDQRules, useRunDQTest } from '../hooks/useDQMetrics';
import type { DQRule } from '../types/data-quality';

export function IncidentDetail() {
  const { selectedRuleId, selectRule } = useDQStore();
  const { data: rules } = useDQRules();
  const runTest = useRunDQTest();

  // 선택된 규칙 찾기
  const rule: DQRule | undefined = rules?.find((r) => r.id === selectedRuleId);

  if (!selectedRuleId || !rule) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-96 bg-card border-l border-border shadow-xl flex flex-col animate-in slide-in-from-right">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <h3 className="text-base font-semibold text-foreground truncate">{rule.name}</h3>
        <button
          type="button"
          onClick={() => selectRule(null)}
          className="p-1 rounded hover:bg-muted"
        >
          <X size={18} className="text-muted-foreground" />
        </button>
      </div>

      {/* 본문 */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* 상태 요약 */}
        <div className="flex items-center gap-3">
          {rule.lastResult?.passed ? (
            <div className="w-10 h-10 rounded-full bg-green-50 dark:bg-green-500/15 flex items-center justify-center">
              <CheckCircle2 size={20} className="text-green-600" />
            </div>
          ) : (
            <div className="w-10 h-10 rounded-full bg-red-50 dark:bg-red-500/15 flex items-center justify-center">
              <AlertTriangle size={20} className="text-red-600" />
            </div>
          )}
          <div>
            <p className="text-sm font-medium text-foreground">
              {rule.lastResult?.passed ? '테스트 통과' : '테스트 실패'}
            </p>
            {rule.lastResult && (
              <p className="text-xs text-muted-foreground">
                {rule.lastResult.failedRows}행 실패 / {rule.lastResult.totalRows}행 전체
              </p>
            )}
          </div>
        </div>

        {/* 속성 */}
        <div className="space-y-3">
          <DetailRow label="테이블" value={rule.tableName} />
          {rule.columnName && <DetailRow label="컬럼" value={rule.columnName} />}
          <DetailRow label="유형" value={rule.type} />
          <DetailRow label="심각도" value={rule.severity} />
          <DetailRow label="레벨" value={rule.level} />
          <DetailRow label="활성" value={rule.enabled ? '예' : '아니오'} />
          {rule.tags && rule.tags.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">태그</p>
              <div className="flex flex-wrap gap-1">
                {rule.tags.map((tag) => (
                  <span key={tag} className="px-2 py-0.5 rounded-full text-[10px] bg-muted text-muted-foreground">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 표현식 */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">표현식</p>
          <pre className="p-3 rounded-md bg-muted text-xs text-foreground font-mono whitespace-pre-wrap break-all">
            {rule.expression}
          </pre>
        </div>

        {/* 마지막 실행 */}
        {rule.lastResult && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock size={12} />
            마지막 실행: {new Date(rule.lastResult.checkedAt).toLocaleString('ko-KR')}
          </div>
        )}
      </div>

      {/* 푸터: 테스트 실행 버튼 */}
      <div className="px-5 py-4 border-t border-border">
        <button
          type="button"
          onClick={() => runTest.mutate(rule.id)}
          disabled={runTest.isPending}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Play size={14} />
          {runTest.isPending ? '실행 중...' : '테스트 실행'}
        </button>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground font-medium">{value}</span>
    </div>
  );
}
