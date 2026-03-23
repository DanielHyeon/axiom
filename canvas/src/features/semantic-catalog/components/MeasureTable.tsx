/**
 * 시멘틱 지표 테이블 — 지표 목록 + SQL 식 + 컴파일/배포 액션
 */
import { useState } from 'react';
import { ChevronDown, ChevronRight, Code2, Play, Rocket } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import type { SemanticMeasure, CompileResult } from '../types/semantic';

interface Props {
  measures: SemanticMeasure[];
  onCompile?: (measureId: string) => Promise<CompileResult>;
  onPublish?: (measureId: string) => void;
  isPublishing?: boolean;
}

export function MeasureTable({ measures, onCompile, onPublish, isPublishing }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [compileResult, setCompileResult] = useState<CompileResult | null>(null);
  const [compiling, setCompiling] = useState(false);

  const handleCompile = async (measureId: string) => {
    if (!onCompile) return;
    setCompiling(true);
    try {
      const result = await onCompile(measureId);
      setCompileResult(result);
    } finally {
      setCompiling(false);
    }
  };

  return (
    <div className="rounded-lg border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="w-8 px-3 py-2" />
            <th className="px-3 py-2 text-left font-medium">지표 ID</th>
            <th className="px-3 py-2 text-left font-medium">이름</th>
            <th className="px-3 py-2 text-left font-medium">타입</th>
            <th className="px-3 py-2 text-left font-medium">엔티티</th>
            <th className="px-3 py-2 text-left font-medium">상태</th>
            <th className="px-3 py-2 text-center font-medium">v</th>
            <th className="px-3 py-2 text-center font-medium">액션</th>
          </tr>
        </thead>
        <tbody>
          {measures.map((m) => {
            const isExpanded = expandedId === m.measure_id;
            return (
              <>
                <tr
                  key={m.measure_id}
                  className="border-b hover:bg-muted/30 cursor-pointer"
                  onClick={() => {
                    setExpandedId(isExpanded ? null : m.measure_id);
                    setCompileResult(null);
                  }}
                >
                  <td className="px-3 py-2">
                    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{m.measure_id}</td>
                  <td className="px-3 py-2 font-medium">{m.name}</td>
                  <td className="px-3 py-2">
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700">{m.measure_type}</span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{m.entity_id}</td>
                  <td className="px-3 py-2"><StatusBadge status={m.status} /></td>
                  <td className="px-3 py-2 text-center tabular-nums">{m.version}</td>
                  <td className="px-3 py-2 text-center">
                    <div className="flex items-center justify-center gap-1">
                      {onCompile && (
                        <button
                          className="p-1 rounded hover:bg-muted"
                          title="컴파일"
                          onClick={(e) => { e.stopPropagation(); handleCompile(m.measure_id); }}
                          disabled={compiling}
                        >
                          <Play className="h-3.5 w-3.5 text-blue-600" />
                        </button>
                      )}
                      {onPublish && m.status !== 'approved' && m.bound_concept_id && (
                        <button
                          className="p-1 rounded hover:bg-muted"
                          title="배포"
                          onClick={(e) => { e.stopPropagation(); onPublish(m.measure_id); }}
                          disabled={isPublishing}
                        >
                          <Rocket className="h-3.5 w-3.5 text-green-600" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {isExpanded && (
                  <tr key={`${m.measure_id}-detail`} className="bg-muted/20">
                    <td colSpan={8} className="px-6 py-3">
                      <div className="space-y-2">
                        {m.description && <p className="text-sm text-muted-foreground">{m.description}</p>}
                        <div className="flex items-start gap-2">
                          <Code2 className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                          <code className="text-xs bg-slate-100 rounded px-2 py-1 block w-full overflow-x-auto">
                            {m.sql_expression}
                          </code>
                        </div>
                        {m.filter_expression && (
                          <div className="text-xs text-muted-foreground">
                            WHERE {m.filter_expression}
                          </div>
                        )}
                        {/* 컴파일 결과 */}
                        {compileResult && expandedId === m.measure_id && (
                          <div className={`rounded-md border p-2 text-xs ${compileResult.valid ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
                            <div className="font-medium mb-1">
                              {compileResult.valid ? 'Valid' : 'Invalid'} — {compileResult.issues.length} issue(s)
                            </div>
                            {compileResult.sql_template && (
                              <pre className="bg-card/60 rounded p-1.5 overflow-x-auto mt-1">{compileResult.sql_template}</pre>
                            )}
                            {compileResult.issues.map((iss, i) => (
                              <div key={i} className={`mt-1 ${iss.severity === 'error' ? 'text-red-700' : 'text-yellow-700'}`}>
                                [{iss.severity}] {iss.code}: {iss.message}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
      {measures.length === 0 && (
        <div className="py-8 text-center text-muted-foreground text-sm">등록된 지표가 없습니다</div>
      )}
    </div>
  );
}
