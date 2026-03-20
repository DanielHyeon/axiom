/**
 * DQTestRunner — 테스트 케이스 생성 다이얼로그
 * KAIR TestCaseModal.vue의 기능을 shadcn/ui Dialog 패턴으로 이식
 * 테스트 레벨 선택 → 테이블 선택 → 테스트 유형 선택 → 생성
 */
import { useState, useMemo } from 'react';
import { X, Search, Pencil } from 'lucide-react';
import { useDQStore } from '../store/useDQStore';
import { useCreateDQRule } from '../hooks/useDQMetrics';
import type { DQRuleType, TestLevel, DQSeverity } from '../types/data-quality';

// 테스트 유형 정의
const TEST_TYPES: { id: DQRuleType; name: string; description: string }[] = [
  { id: 'not_null', name: 'Null 체크', description: '컬럼 값이 NULL이 아닌지 검증합니다.' },
  { id: 'unique', name: 'Unique 체크', description: '컬럼 값의 유일성을 검증합니다.' },
  { id: 'range', name: 'Range 체크', description: '컬럼 값이 지정된 범위 내에 있는지 검증합니다.' },
  { id: 'regex', name: 'Format 체크', description: '컬럼 값이 지정된 정규식 패턴에 맞는지 검증합니다.' },
  { id: 'custom_sql', name: 'Custom SQL', description: '커스텀 SQL 쿼리가 0행을 반환하는지 검증합니다.' },
];

export function DQTestRunner() {
  const { showCreateDialog, setShowCreateDialog } = useDQStore();
  const createRule = useCreateDQRule();

  // 폼 상태
  const [level, setLevel] = useState<TestLevel>('column');
  const [tableName, setTableName] = useState('');
  const [columnName, setColumnName] = useState('');
  const [testType, setTestType] = useState<DQRuleType | ''>('');
  const [testTypeSearch, setTestTypeSearch] = useState('');
  const [expression, setExpression] = useState('');
  const [name, setName] = useState('');
  const [severity, setSeverity] = useState<DQSeverity>('warning');

  // 테스트 유형 필터링
  const filteredTypes = useMemo(() => {
    if (!testTypeSearch) return TEST_TYPES;
    const q = testTypeSearch.toLowerCase();
    return TEST_TYPES.filter(
      (t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q),
    );
  }, [testTypeSearch]);

  // 초기화
  const resetForm = () => {
    setLevel('column');
    setTableName('');
    setColumnName('');
    setTestType('');
    setTestTypeSearch('');
    setExpression('');
    setName('');
    setSeverity('warning');
  };

  // 생성 처리
  const handleCreate = () => {
    if (!testType || !tableName || !name) return;
    createRule.mutate(
      {
        name,
        tableName,
        columnName: columnName || undefined,
        type: testType,
        expression: expression || `${columnName || tableName} ${testType}`,
        severity,
        level,
      },
      {
        onSuccess: () => {
          resetForm();
          setShowCreateDialog(false);
        },
      },
    );
  };

  if (!showCreateDialog) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowCreateDialog(false)}>
      <div
        className="w-full max-w-4xl max-h-[90vh] bg-card border border-border rounded-lg shadow-xl flex flex-col animate-in fade-in zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">테스트 케이스 추가</h2>
          <button type="button" onClick={() => setShowCreateDialog(false)} className="p-1 rounded hover:bg-muted">
            <X size={20} className="text-muted-foreground" />
          </button>
        </div>

        {/* 본문: 좌측 폼 + 우측 가이드 */}
        <div className="flex-1 grid grid-cols-[1fr_300px] overflow-hidden">
          {/* 좌측: 폼 */}
          <div className="p-6 overflow-y-auto space-y-6">
            {/* 1. 테스트 레벨 */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                테스트 레벨 <span className="text-destructive">*</span>
              </label>
              <div className="grid grid-cols-3 gap-3">
                {(['table', 'column', 'custom'] as TestLevel[]).map((lv) => (
                  <button
                    key={lv}
                    type="button"
                    onClick={() => setLevel(lv)}
                    className={`relative p-3 rounded-lg border-2 text-left transition-colors ${
                      level === lv
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <p className="text-sm font-semibold text-primary">
                      {lv === 'table' ? '테이블 레벨' : lv === 'column' ? '컬럼 레벨' : '커스텀'}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {lv === 'table' ? '테이블에 적용' : lv === 'column' ? '컬럼에 적용' : 'SQL 직접 작성'}
                    </p>
                    {level === lv && (
                      <div className="absolute top-2 right-2 w-5 h-5 bg-primary rounded-full flex items-center justify-center">
                        <span className="text-white text-xs">&#10003;</span>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* 2. 테스트 이름 */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                테스트 이름 <span className="text-destructive">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="check_column_not_null"
                className="w-full px-3 py-2.5 bg-secondary border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
            </div>

            {/* 3. 테이블 선택 */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                테이블 <span className="text-destructive">*</span>
              </label>
              <input
                type="text"
                value={tableName}
                onChange={(e) => setTableName(e.target.value)}
                placeholder="customer_360"
                className="w-full px-3 py-2.5 bg-secondary border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
            </div>

            {/* 4. 컬럼 (레벨이 column일 때) */}
            {level === 'column' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">컬럼</label>
                <input
                  type="text"
                  value={columnName}
                  onChange={(e) => setColumnName(e.target.value)}
                  placeholder="email"
                  className="w-full px-3 py-2.5 bg-secondary border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
                />
              </div>
            )}

            {/* 5. 심각도 */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">심각도</label>
              <div className="flex gap-2">
                {(['critical', 'warning', 'info'] as DQSeverity[]).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSeverity(s)}
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                      severity === s
                        ? s === 'critical'
                          ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                          : s === 'warning'
                            ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-400'
                            : 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400'
                        : 'bg-secondary text-muted-foreground hover:bg-muted'
                    }`}
                  >
                    {s.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* 6. 테스트 유형 선택 */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-foreground">
                  테스트 유형 <span className="text-destructive">*</span>
                </label>
                <button
                  type="button"
                  onClick={() => setTestType('custom_sql')}
                  className="flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  <Pencil size={12} />
                  커스텀 SQL
                </button>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 bg-secondary border border-primary rounded-md">
                <Search size={14} className="text-muted-foreground" />
                <input
                  type="text"
                  value={testTypeSearch}
                  onChange={(e) => setTestTypeSearch(e.target.value)}
                  placeholder="테스트 유형 검색"
                  className="flex-1 bg-transparent border-none text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                />
              </div>
              <div className="max-h-48 overflow-y-auto border border-border rounded-md bg-secondary">
                {filteredTypes.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTestType(t.id)}
                    className={`w-full text-left px-4 py-3 border-b border-border last:border-b-0 transition-colors ${
                      testType === t.id ? 'bg-primary/10' : 'hover:bg-muted'
                    }`}
                  >
                    <p className={`text-sm font-medium ${testType === t.id ? 'text-primary' : 'text-foreground'}`}>
                      {t.name}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">{t.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* 7. 커스텀 SQL (custom_sql 타입일 때) */}
            {testType === 'custom_sql' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">SQL 표현식</label>
                <textarea
                  value={expression}
                  onChange={(e) => setExpression(e.target.value)}
                  placeholder="SELECT COUNT(*) FROM table WHERE condition"
                  rows={4}
                  className="w-full px-3 py-2.5 bg-secondary border border-border rounded-md text-sm text-foreground font-mono placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-y"
                />
              </div>
            )}
          </div>

          {/* 우측: 가이드 패널 */}
          <aside className="p-5 bg-muted/30 border-l border-border overflow-y-auto">
            <div className="space-y-4">
              <div className="pl-3 border-l-2 border-primary">
                <h4 className="text-sm font-semibold text-foreground mb-1">테스트 유형</h4>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  데이터 품질 요구사항에 맞는 테스트 유형을 선택하세요. 테이블/컬럼 레벨에 따라 사용 가능한 유형이 달라집니다.
                </p>
                <ul className="mt-2 space-y-1 text-xs text-muted-foreground list-disc list-inside">
                  <li>값 유효성 검사</li>
                  <li>유일성 체크</li>
                  <li>Null 체크</li>
                  <li>패턴 매칭</li>
                  <li>범위 검증</li>
                  <li>커스텀 SQL</li>
                </ul>
              </div>
              <div className="pl-3 border-l-2 border-primary">
                <h4 className="text-sm font-semibold text-foreground mb-1">이름 규칙</h4>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  고유한 테스트 이름을 지정하세요. 문자로 시작하고, 문자/숫자/밑줄만 사용 가능합니다.
                </p>
              </div>
            </div>
          </aside>
        </div>

        {/* 푸터 */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border">
          <button
            type="button"
            onClick={() => setShowCreateDialog(false)}
            className="px-4 py-2 text-sm rounded-md border border-border text-muted-foreground hover:bg-muted transition-colors"
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={!testType || !tableName || !name || createRule.isPending}
            className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {createRule.isPending ? '생성 중...' : '생성'}
          </button>
        </div>
      </div>
    </div>
  );
}
