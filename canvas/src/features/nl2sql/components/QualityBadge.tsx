/**
 * 품질 경고 배지 — NL2SQL 결과에 시멘틱 계약 품질 경고를 표시
 *
 * 시멘틱 컨텍스트가 사용되었는지, 품질 경고가 있는지 시각적으로 알려준다.
 */
import { useState } from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';

interface Props {
  /** 시멘틱 계약 컨텍스트 사용 여부 */
  semanticContextUsed?: boolean;
  /** 품질 경고 목록 */
  qualityWarnings?: string[];
  /** 의도 분류 결과 */
  intentType?: string;
}

export function QualityBadge({ semanticContextUsed, qualityWarnings = [], intentType }: Props) {
  const [expanded, setExpanded] = useState(false);
  const hasWarnings = qualityWarnings.length > 0;

  return (
    <div className="flex flex-col gap-1">
      {/* 배지 행 */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* 시멘틱 컨텍스트 상태 */}
        {semanticContextUsed ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-50 border border-green-200 px-2 py-0.5 text-xs text-green-700">
            <ShieldCheck className="h-3 w-3" />
            시멘틱 계약 기반
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-50 border border-slate-200 px-2 py-0.5 text-xs text-slate-500">
            <ShieldAlert className="h-3 w-3" />
            Raw 스키마 기반
          </span>
        )}

        {/* 의도 분류 */}
        {intentType && intentType !== 'general' && (
          <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 border border-violet-200 px-2 py-0.5 text-xs text-violet-700">
            <Sparkles className="h-3 w-3" />
            {intentType}
          </span>
        )}

        {/* 품질 경고 토글 */}
        {hasWarnings && (
          <button
            className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs text-amber-700 hover:bg-amber-100 transition-colors"
            onClick={() => setExpanded(!expanded)}
          >
            <AlertTriangle className="h-3 w-3" />
            {qualityWarnings.length}건 품질 경고
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        )}
      </div>

      {/* 경고 상세 (확장 시) */}
      {expanded && hasWarnings && (
        <div className="rounded-md border border-amber-200 bg-amber-50/50 p-2 text-xs space-y-1">
          {qualityWarnings.map((w, i) => (
            <div key={i} className="flex items-start gap-1.5 text-amber-800">
              <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
