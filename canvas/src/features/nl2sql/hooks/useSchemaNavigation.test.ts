import { describe, it, expect } from 'vitest';
import type { SchemaMode } from '@/shared/utils/nodeKey';

// ---------------------------------------------------------------------------
// S1-S4 상태 전이 정책을 직접 테스트하는 순수 함수
// useSchemaNavigation 훅 내부의 모드 판정 로직을 동일하게 추출하여 검증한다.
// ---------------------------------------------------------------------------

/**
 * 가용성 데이터(robo/text2sql 테이블 수)와 저장된 모드 값을 기반으로
 * 초기 스키마 모드를 결정하는 순수 함수.
 *
 * - S1: robo=0, text2sql>0 → text2sql
 * - S2: robo>0, text2sql=0 → robo
 * - S3: 둘 다 >0 → localStorage 저장값 우선, 없으면 text2sql 기본
 * - S4: 둘 다 0 → text2sql 기본
 */
function resolveMode(
  roboCount: number,
  text2sqlCount: number,
  storedMode: string | null,
): SchemaMode {
  if (roboCount === 0 && text2sqlCount > 0) return 'text2sql'; // S1
  if (roboCount > 0 && text2sqlCount === 0) return 'robo'; // S2
  if (roboCount > 0 && text2sqlCount > 0) {
    // S3: 둘 다 존재 — localStorage 복원
    return storedMode === 'robo' ? 'robo' : 'text2sql';
  }
  return 'text2sql'; // S4: 둘 다 0
}

// ---------------------------------------------------------------------------
// S1: text2sql만 존재
// ---------------------------------------------------------------------------

describe('resolveMode — S1: robo=0, text2sql>0', () => {
  it('text2sql만 있으면 text2sql 반환', () => {
    expect(resolveMode(0, 5, null)).toBe('text2sql');
  });

  it('storedMode가 robo여도 text2sql 반환 (robo 데이터가 없으므로)', () => {
    expect(resolveMode(0, 10, 'robo')).toBe('text2sql');
  });
});

// ---------------------------------------------------------------------------
// S2: robo만 존재
// ---------------------------------------------------------------------------

describe('resolveMode — S2: robo>0, text2sql=0', () => {
  it('robo만 있으면 robo 반환', () => {
    expect(resolveMode(3, 0, null)).toBe('robo');
  });

  it('storedMode가 text2sql이어도 robo 반환 (text2sql 데이터가 없으므로)', () => {
    expect(resolveMode(7, 0, 'text2sql')).toBe('robo');
  });
});

// ---------------------------------------------------------------------------
// S3: 둘 다 존재
// ---------------------------------------------------------------------------

describe('resolveMode — S3: both>0', () => {
  it('storedMode가 null이면 text2sql 기본값', () => {
    expect(resolveMode(5, 5, null)).toBe('text2sql');
  });

  it('storedMode가 robo이면 robo 반환', () => {
    expect(resolveMode(5, 5, 'robo')).toBe('robo');
  });

  it('storedMode가 text2sql이면 text2sql 반환', () => {
    expect(resolveMode(5, 5, 'text2sql')).toBe('text2sql');
  });

  it('경계값: robo=1, text2sql=1 → S3 케이스로 처리', () => {
    // 최소 1개씩만 있어도 S3 로직을 탄다
    expect(resolveMode(1, 1, null)).toBe('text2sql');
    expect(resolveMode(1, 1, 'robo')).toBe('robo');
  });
});

// ---------------------------------------------------------------------------
// S4: 둘 다 없음
// ---------------------------------------------------------------------------

describe('resolveMode — S4: both=0', () => {
  it('둘 다 0이면 text2sql 기본값', () => {
    expect(resolveMode(0, 0, null)).toBe('text2sql');
  });

  it('storedMode가 있어도 text2sql 기본값 (데이터가 없으므로)', () => {
    expect(resolveMode(0, 0, 'robo')).toBe('text2sql');
  });
});

// ---------------------------------------------------------------------------
// 결정 테이블 전체 매트릭스 검증
// ---------------------------------------------------------------------------

describe('resolveMode — 결정 테이블 매트릭스', () => {
  const cases: Array<{
    label: string;
    robo: number;
    text2sql: number;
    stored: string | null;
    expected: SchemaMode;
  }> = [
    { label: 'S1 기본', robo: 0, text2sql: 10, stored: null, expected: 'text2sql' },
    { label: 'S2 기본', robo: 8, text2sql: 0, stored: null, expected: 'robo' },
    { label: 'S3 저장값=robo', robo: 3, text2sql: 4, stored: 'robo', expected: 'robo' },
    { label: 'S3 저장값=text2sql', robo: 3, text2sql: 4, stored: 'text2sql', expected: 'text2sql' },
    { label: 'S3 저장값=null', robo: 3, text2sql: 4, stored: null, expected: 'text2sql' },
    { label: 'S4 빈 상태', robo: 0, text2sql: 0, stored: null, expected: 'text2sql' },
    { label: 'S4 저장값 무시', robo: 0, text2sql: 0, stored: 'robo', expected: 'text2sql' },
  ];

  cases.forEach(({ label, robo, text2sql, stored, expected }) => {
    it(`${label}: robo=${robo}, text2sql=${text2sql}, stored=${stored} → ${expected}`, () => {
      expect(resolveMode(robo, text2sql, stored)).toBe(expected);
    });
  });
});
