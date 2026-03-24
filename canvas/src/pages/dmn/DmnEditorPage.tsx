/**
 * DMN 결정 에디터 페이지.
 * KG-1: 결정 테이블 목록 + 상세 편집 + 테스트 실행.
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/shared/components/LoadingSpinner';
import { EmptyState } from '@/shared/components/EmptyState';
import { Badge } from '@/components/ui/badge';
import { DmnTableEditor } from '@/features/dmn/components/DmnTableEditor';
import { useDmnTables, useDmnTable, useUpdateDmnTable, useExecuteDmnTest } from '@/features/dmn/hooks/useDmnTable';
import type { DmnTestResult } from '@/features/dmn/types/dmn';
import { TableProperties, Plus , FileText } from 'lucide-react';

export function DmnEditorPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: tables = [], isLoading } = useDmnTables();
  const { data: selectedTable } = useDmnTable(selectedId ?? '');
  const updateMutation = useUpdateDmnTable(selectedId ?? '');
  const testMutation = useExecuteDmnTest(selectedId ?? '');
  const [testResult, setTestResult] = useState<DmnTestResult | null>(null);

  if (isLoading) return <LoadingSpinner size="lg" label="결정 테이블 로딩 중" />;

  return (
    <div className="flex h-full">
      {/* 좌측: 테이블 목록 */}
      <div className="w-64 shrink-0 border-r border-border bg-card overflow-auto p-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-sm font-semibold">결정 테이블</h1>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" aria-label="새 테이블">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {tables.length === 0 ? (
          <p className="text-xs text-muted-foreground">테이블이 없습니다</p>
        ) : (
          <div className="space-y-1">
            {tables.map((t) => (
              <button
                key={t.id}
                onClick={() => { setSelectedId(t.id); setTestResult(null); }}
                className={`w-full text-left rounded-md px-3 py-2 text-sm transition-colors ${
                  selectedId === t.id ? 'bg-primary/10 text-primary' : 'hover:bg-muted text-foreground'
                }`}
              >
                <div className="flex items-center gap-2">
                  <TableProperties className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{t.name}</span>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  <Badge variant="outline" className="text-[10px] h-4">{t.hitPolicy}</Badge>
                  <span className="text-[10px] text-muted-foreground">{t.rules.length}규칙</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 우측: 에디터 */}
      <div className="flex-1 overflow-auto p-6">
        {!selectedTable ? (
          <EmptyState
            icon={FileText}
            title="결정 테이블을 선택하세요"
            description="좌측 목록에서 테이블을 클릭하면 편집할 수 있습니다"
          />
        ) : (
          <DmnTableEditor
            table={selectedTable}
            onSave={(updates) => updateMutation.mutate(updates)}
            onTest={async (req) => {
              const result = await testMutation.mutateAsync(req);
              setTestResult(result);
            }}
            testResult={testResult}
            isSaving={updateMutation.isPending}
          />
        )}
      </div>
    </div>
  );
}
