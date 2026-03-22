/**
 * 품질 경고 배지 — NL2SQL 결과에 시멘틱 계약 품질 경고를 표시
 *
 * 시멘틱 컨텍스트가 사용되었는지, 품질 경고가 있는지,
 * 그리고 Sprint 2의 품질 신뢰 등급을 시각적으로 알려준다.
 */
import { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Shield,
  ShieldOff,
  ShieldBan,
  BookOpen,
  Link2,
} from 'lucide-react';

/** 품질 신뢰 등급 타입 */
type TrustTier = 'TRUSTED' | 'CAUTION' | 'REFERENCE_ONLY' | 'BLOCKED';

interface Props {
  /** 시멘틱 계약 컨텍스트 사용 여부 */
  semanticContextUsed?: boolean;
  /** 품질 경고 목록 */
  qualityWarnings?: string[];
  /** 의도 분류 결과 */
  intentType?: string;
  /** Sprint 2: 품질 신뢰 등급 */
  qualityGrade?: string;
  /** Sprint 2: 품질 최종 점수 (0~100) */
  qualityScore?: number;
  /** Sprint 2: 품질 등급 안내 문구 */
  qualityBanner?: string;
  /** Sprint 4: 의도 분류 신뢰도 (0.0~1.0) */
  intentConfidence?: number;
  /** Sprint 4: 동의어 매칭 수 */
  synonymMatches?: number;
  /** Sprint 4: 폴백 모드 */
  fallbackMode?: string;
}

/** 등급별 배지 스타일 설정 */
const TIER_STYLES: Record<TrustTier, {
  bg: string;
  border: string;
  text: string;
  label: string;
  Icon: typeof ShieldCheck;
}> = {
  TRUSTED: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-700',
    label: '신뢰 가능',
    Icon: ShieldCheck,
  },
  CAUTION: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-300',
    text: 'text-yellow-700',
    label: '주의 필요',
    Icon: Shield,
  },
  REFERENCE_ONLY: {
    bg: 'bg-orange-50',
    border: 'border-orange-300',
    text: 'text-orange-700',
    label: '참고용',
    Icon: ShieldOff,
  },
  BLOCKED: {
    bg: 'bg-red-50',
    border: 'border-red-300',
    text: 'text-red-700',
    label: '사용 제한',
    Icon: ShieldBan,
  },
};

export function QualityBadge({
  semanticContextUsed,
  qualityWarnings = [],
  intentType,
  qualityGrade,
  qualityScore,
  qualityBanner,
  intentConfidence,
  synonymMatches,
  fallbackMode,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const hasWarnings = qualityWarnings.length > 0;

  // 등급 스타일 결정 (유효한 등급인 경우만)
  const tierStyle = qualityGrade && (qualityGrade as TrustTier) in TIER_STYLES
    ? TIER_STYLES[qualityGrade as TrustTier]
    : null;

  return (
    <div className="flex flex-col gap-1">
      {/* 배지 행 */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Sprint 2: 품질 신뢰 등급 배지 — 있으면 시멘틱 컨텍스트 배지를 대체 */}
        {tierStyle ? (
          <span
            className={`inline-flex items-center gap-1 rounded-full ${tierStyle.bg} border ${tierStyle.border} px-2 py-0.5 text-xs ${tierStyle.text}`}
            title={qualityBanner || tierStyle.label}
          >
            <tierStyle.Icon className="h-3 w-3" />
            {tierStyle.label}
            {qualityScore != null && (
              <span className="ml-0.5 font-medium">{Math.round(qualityScore)}점</span>
            )}
          </span>
        ) : (
          /* 기존 시멘틱 컨텍스트 배지 (등급 정보가 없을 때 폴백) */
          semanticContextUsed ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-50 border border-green-200 px-2 py-0.5 text-xs text-green-700">
              <ShieldCheck className="h-3 w-3" />
              시멘틱 계약 기반
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-50 border border-slate-200 px-2 py-0.5 text-xs text-slate-500">
              <ShieldAlert className="h-3 w-3" />
              Raw 스키마 기반
            </span>
          )
        )}

        {/* 의도 분류 + Sprint 4: 신뢰도 퍼센트 표시 */}
        {intentType && intentType !== 'general' && (
          <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 border border-violet-200 px-2 py-0.5 text-xs text-violet-700">
            <Sparkles className="h-3 w-3" />
            {intentType}
            {intentConfidence != null && (
              <span className="ml-0.5 font-medium opacity-75">
                {Math.round(intentConfidence * 100)}%
              </span>
            )}
          </span>
        )}

        {/* Sprint 4: 동의어 매칭 수 배지 */}
        {synonymMatches != null && synonymMatches > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-cyan-50 border border-cyan-200 px-2 py-0.5 text-xs text-cyan-700">
            <Link2 className="h-3 w-3" />
            동의어 {synonymMatches}건
          </span>
        )}

        {/* Sprint 4: 폴백 모드 경고 (NONE이 아닐 때만 표시) */}
        {fallbackMode && fallbackMode !== 'NONE' && (
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
              fallbackMode === 'REFERENCE_ONLY'
                ? 'bg-orange-50 border border-orange-200 text-orange-700'
                : 'bg-yellow-50 border border-yellow-200 text-yellow-700'
            }`}
          >
            <BookOpen className="h-3 w-3" />
            {fallbackMode === 'REFERENCE_ONLY' ? '참고용' : '안전 모드'}
          </span>
        )}

        {/* 품질 경고 토글 */}
        {hasWarnings && (
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs text-amber-700 hover:bg-amber-100 transition-colors"
            onClick={() => setExpanded(!expanded)}
          >
            <AlertTriangle className="h-3 w-3" />
            {qualityWarnings.length}건 품질 경고
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        )}
      </div>

      {/* Sprint 2: 품질 등급 안내 배너 (CAUTION 이상일 때만 표시) */}
      {qualityBanner && qualityGrade && qualityGrade !== 'TRUSTED' && (
        <div
          className={`rounded-md border px-2 py-1.5 text-xs ${
            qualityGrade === 'BLOCKED'
              ? 'border-red-200 bg-red-50/50 text-red-700'
              : qualityGrade === 'REFERENCE_ONLY'
                ? 'border-orange-200 bg-orange-50/50 text-orange-700'
                : 'border-yellow-200 bg-yellow-50/50 text-yellow-700'
          }`}
        >
          {qualityBanner}
        </div>
      )}

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
