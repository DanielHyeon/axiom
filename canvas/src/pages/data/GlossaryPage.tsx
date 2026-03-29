/**
 * GlossaryPage — 비즈니스 글로서리 페이지 (디자인 리뉴얼)
 *
 * .pen 디자인 매칭:
 * - 수직 레이아웃, 24px 패딩, 48px 좌우, 16px 갭
 * - 알파벳 내비게이션: 32x32 버튼 가로 배치 (활성: primary fill + 흰 글자, 비활성: border만)
 * - 용어 목록: 흰색 카드, 12px radius, 높이 채움
 * - 용어 카드: 16px/20px 패딩, 하단 border, 이름 Geist 14px medium, 설명 Geist 12px secondary
 *
 * 백엔드 연동: GET /proxy/weaver/api/v1/metadata/glossary (기존 glossaryApi 재사용)
 */

import { useState, useMemo, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import { useGlossaries, useTerms } from '@/features/glossary/hooks/useGlossary';
import { useGlossaryStore } from '@/features/glossary/store/useGlossaryStore';
import type { GlossaryTerm } from '@/features/glossary/types/glossary';

// 알파벳 내비게이션 문자 목록
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

export const GlossaryPage: React.FC = () => {
  const { t } = useTranslation();

  // 활성 알파벳 필터
  const [activeLetter, setActiveLetter] = useState<string | null>(null);

  // 스크롤 컨테이너 참조
  const scrollRef = useRef<HTMLDivElement>(null);

  // 기존 스토어 & 훅 재사용
  const { selectedGlossary, setSelectedGlossary } = useGlossaryStore();
  const { data: glossaryData, isLoading: glossaryLoading } = useGlossaries();
  const glossaries = glossaryData?.glossaries ?? [];

  // 첫 용어집 자동 선택 — useEffect로 래핑하여 렌더 중 상태 변경 방지
  useEffect(() => {
    if (!selectedGlossary && glossaries.length > 0) {
      setSelectedGlossary(glossaries[0]);
    }
  }, [selectedGlossary, glossaries, setSelectedGlossary]);

  // 용어 목록 조회
  const { data: termData, isLoading: termsLoading } = useTerms(
    selectedGlossary?.id ?? null,
  );
  const terms: GlossaryTerm[] = termData?.terms ?? [];

  // 알파벳별 그룹핑 + 활성 알파벳 목록
  const { groupedTerms, activeLetters } = useMemo(() => {
    const groups: Record<string, GlossaryTerm[]> = {};
    for (const term of terms) {
      const firstChar = term.name.charAt(0).toUpperCase();
      const key = /[A-Z]/.test(firstChar) ? firstChar : '#';
      if (!groups[key]) groups[key] = [];
      groups[key].push(term);
    }
    // 각 그룹 내 이름순 정렬
    for (const key of Object.keys(groups)) {
      groups[key].sort((a, b) => a.name.localeCompare(b.name));
    }
    return {
      groupedTerms: groups,
      activeLetters: new Set(Object.keys(groups)),
    };
  }, [terms]);

  // 필터된 용어 목록 (알파벳 선택 시 해당 글자만, 미선택 시 전체)
  const filteredEntries = useMemo(() => {
    if (activeLetter) {
      const termsForLetter = groupedTerms[activeLetter];
      return termsForLetter ? [[activeLetter, termsForLetter] as const] : [];
    }
    // 알파벳 순서대로 모든 그룹
    return ALPHABET.filter((l) => groupedTerms[l])
      .map((l) => [l, groupedTerms[l]] as const);
  }, [activeLetter, groupedTerms]);

  /** 알파벳 버튼 클릭 — 토글 방식 (같은 글자 다시 누르면 해제) */
  const handleLetterClick = (letter: string) => {
    setActiveLetter((prev) => (prev === letter ? null : letter));
    // 스크롤 최상단으로 이동
    scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const isLoading = glossaryLoading || termsLoading;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 본문 — 24px 상하 패딩, 48px 좌우, 16px 갭 */}
      <div className="flex flex-col flex-1 min-h-0 gap-4 px-12 py-6">
        {/* 알파벳 내비게이션 — 32x32 버튼 가로 나열, 4px 갭 */}
        <nav
          className="flex flex-wrap gap-1"
          role="navigation"
          aria-label={t('glossary.alphabetNav', '알파벳 내비게이션')}
        >
          {ALPHABET.map((letter) => {
            const isActive = activeLetter === letter;
            const hasTerms = activeLetters.has(letter);

            return (
              <button
                type="button"
                key={letter}
                onClick={() => handleLetterClick(letter)}
                disabled={!hasTerms}
                aria-label={`${letter} ${hasTerms ? '' : '(없음)'}`}
                className={[
                  'w-8 h-8 flex items-center justify-center rounded-md text-xs font-semibold transition-all',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : hasTerms
                      ? 'border border-border text-text-secondary hover:border-primary hover:text-primary'
                      : 'border border-border text-border cursor-default opacity-50',
                ].join(' ')}
              >
                {letter}
              </button>
            );
          })}
        </nav>

        {/* 용어 목록 카드 — 흰색 배경, 12px radius, 1px border, 높이 채움 */}
        <div
          ref={scrollRef}
          className="flex-1 min-h-0 overflow-y-auto rounded-xl bg-card border border-border"
        >
          {/* 로딩 상태 */}
          {isLoading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-text-placeholder" />
            </div>
          )}

          {/* 빈 상태 */}
          {!isLoading && terms.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 gap-2">
              <p className="text-sm text-text-placeholder">
                {t('glossary.term.empty', '등록된 용어가 없습니다.')}
              </p>
            </div>
          )}

          {/* 용어 렌더링 */}
          {!isLoading &&
            filteredEntries.map(([letter, letterTerms]) => (
              <div key={letter}>
                {letterTerms.map((term) => (
                  <div
                    key={term.id}
                    className="flex flex-col gap-1 px-5 py-4 border-b border-border last:border-b-0"
                  >
                    {/* 용어 이름 — Geist 14px medium */}
                    <span className="text-sm font-medium text-foreground">
                      {term.name}
                    </span>
                    {/* 설명 — Geist 12px secondary, lineHeight 1.4 */}
                    {term.definition && (
                      <span className="text-xs text-text-secondary leading-[1.4]">
                        {term.definition}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ))}
        </div>
      </div>
    </div>
  );
};
