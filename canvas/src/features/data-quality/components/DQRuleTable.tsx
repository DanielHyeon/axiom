/**
 * DQRuleTable — DQ 규칙 목록 테이블
 * KAIR DataQuality.vue의 test-cases-table 섹션을 이식
 * 정렬, 검색, 인시던트 뱃지, 테스트 실행 버튼 포함
 */
import { useState, useMemo } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  Play,
  MoreVertical,
  Search,
  Loader2,
} from 'lucide-react';
import { useDQRules, useRunDQTest } from '../hooks/useDQMetrics';
import { useDQStore } from '../store/useDQStore';
import type { DQRule } from '../types/data-quality';

// 정렬 키
type SortKey = 'name' | 'lastRun' | 'status';

export function DQRuleTable() {
  const { filteredRules, isLoading } = useDQRules();
  const { filters, setSearchQuery, selectRule } = useDQStore();
  const runTest = useRunDQTest();
  const [sortKey, setSortKey] = useState<SortKey>('lastRun');
  const [sortAsc, setSortAsc] = useState(false);

  // 정렬 적용
  const sortedRules = useMemo(() => {
    const rules = [...filteredRules];
    rules.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') {
        cmp = a.name.localeCompare(b.name);
      } else if (sortKey === 'lastRun') {
        const aDate = a.lastResult?.checkedAt ?? '';
        const bDate = b.lastResult?.checkedAt ?? '';
        cmp = aDate.localeCompare(bDate);
      } else if (sortKey === 'status') {
        const aStatus = a.lastResult?.passed ? 1 : 0;
        const bStatus = b.lastResult?.passed ? 1 : 0;
        cmp = aStatus - bStatus;
      }
      return sortAsc ? cmp : -cmp;
    });
    return rules;
  }, [filteredRules, sortKey, sortAsc]);

  // 정렬 토글
  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  // 상태 뱃지 렌더러
  const StatusBadge = ({ rule }: { rule: DQRule }) => {
    if (!rule.lastResult) {
      return <span className="text-xs text-muted-foreground">미실행</span>;
    }
    if (rule.lastResult.passed) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-400">
          <CheckCircle2 size={12} />
          Success
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-400">
        <AlertTriangle size={12} />
        Failed
      </span>
    );
  };

  // 실패 사유
  const FailureReason = ({ rule }: { rule: DQRule }) => {
    if (!rule.lastResult || rule.lastResult.passed) {
      return <span className="text-xs text-muted-foreground">- -</span>;
    }
    const pct = ((rule.lastResult.failedRows / rule.lastResult.totalRows) * 100).toFixed(2);
    return (
      <span className="text-xs text-muted-foreground">
        {rule.lastResult.failedRows}행 실패 ({pct}%)
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
        <Loader2 className="animate-spin" size={16} />
        <span className="text-sm">규칙 목록 로딩 중...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col border border-border rounded-lg bg-card overflow-hidden">
      {/* 섹션 헤더 */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div>
          <h2 className="text-base font-semibold text-foreground">테스트 케이스 인사이트</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            구성된 테스트 검증을 기반으로 데이터셋 상태를 확인합니다.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-secondary rounded border border-border min-w-[240px]">
          <Search size={14} className="text-muted-foreground shrink-0" />
          <input
            type="text"
            value={filters.searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="테스트 케이스 검색"
            className="flex-1 bg-transparent border-none text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
        </div>
      </div>

      {/* 테이블 */}
      <div className="overflow-auto flex-1">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-muted/50">
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                <button type="button" onClick={() => toggleSort('status')} className="hover:text-foreground">
                  현황 {sortKey === 'status' ? (sortAsc ? '↑' : '↓') : ''}
                </button>
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                실패 사유
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                <button type="button" onClick={() => toggleSort('lastRun')} className="hover:text-foreground">
                  마지막 실행 {sortKey === 'lastRun' ? (sortAsc ? '↑' : '↓') : ''}
                </button>
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                <button type="button" onClick={() => toggleSort('name')} className="hover:text-foreground">
                  이름 {sortKey === 'name' ? (sortAsc ? '↑' : '↓') : ''}
                </button>
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                테이블
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                컬럼
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                심각도
              </th>
              <th className="px-4 py-3 w-20" />
            </tr>
          </thead>
          <tbody>
            {sortedRules.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-sm text-muted-foreground">
                  테스트 케이스가 없습니다.
                </td>
              </tr>
            ) : (
              sortedRules.map((rule) => (
                <tr
                  key={rule.id}
                  className="border-b border-border hover:bg-muted/30 cursor-pointer transition-colors"
                  onClick={() => selectRule(rule.id)}
                >
                  <td className="px-4 py-3">
                    <StatusBadge rule={rule} />
                  </td>
                  <td className="px-4 py-3">
                    <FailureReason rule={rule} />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                    {rule.lastResult?.checkedAt
                      ? new Date(rule.lastResult.checkedAt).toLocaleString('ko-KR')
                      : '- -'}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm font-medium text-primary hover:underline">{rule.name}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{rule.tableName}</td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{rule.columnName ?? '-'}</td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={rule.severity} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        title="테스트 실행"
                        onClick={(e) => {
                          e.stopPropagation();
                          runTest.mutate(rule.id);
                        }}
                        disabled={runTest.isPending}
                        className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-foreground disabled:opacity-50"
                      >
                        {runTest.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                      </button>
                      <button
                        type="button"
                        className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreVertical size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** 심각도 뱃지 */
function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    critical: 'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-400',
    warning: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-400',
    info: 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400',
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium uppercase ${styles[severity] ?? styles.info}`}>
      {severity}
    </span>
  );
}
