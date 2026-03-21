/**
 * PivotResultGrid 컴포넌트 테스트.
 *
 * 결과 테이블, 로딩 상태, 에러 상태, 빈 결과 등 다양한 상태를 검증한다.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PivotResultGrid } from './PivotResultGrid';
import type { PivotResult } from '../hooks/usePivot';

// ─── 테스트 헬퍼 ──────────────────────────────────────────

function makeResult(overrides: Partial<PivotResult> = {}): PivotResult {
  return {
    sql: 'SELECT year, SUM(revenue) FROM dw.fact_table GROUP BY year',
    columns: ['year', 'revenue'],
    rows: [['2025', 100000], ['2026', 150000]],
    row_count: 2,
    execution_time_ms: 42,
    ...overrides,
  };
}

// ─── 초기 상태 (result=null) ──────────────────────────────

describe('PivotResultGrid — 초기 상태', () => {
  it('결과 없을 때 안내 메시지를 표시한다', () => {
    render(<PivotResultGrid result={null} isLoading={false} />);

    expect(screen.getByText('피벗을 실행하면 결과가 여기에 표시됩니다')).toBeDefined();
  });
});

// ─── 로딩 상태 ────────────────────────────────────────────

describe('PivotResultGrid — 로딩 상태', () => {
  it('로딩 중일 때 스피너를 표시한다', () => {
    const { container } = render(<PivotResultGrid result={null} isLoading={true} />);

    // animate-spin 클래스를 가진 스피너 요소 확인
    const spinner = container.querySelector('.animate-spin');
    expect(spinner).not.toBeNull();
  });

  it('로딩 중일 때 안내 메시지를 표시하지 않는다', () => {
    render(<PivotResultGrid result={null} isLoading={true} />);

    expect(screen.queryByText('피벗을 실행하면 결과가 여기에 표시됩니다')).toBeNull();
  });
});

// ─── 에러 상태 ────────────────────────────────────────────

describe('PivotResultGrid — 에러 상태', () => {
  it('에러 메시지를 표시한다', () => {
    const result = makeResult({ error: '쿼리 실행 중 오류가 발생했습니다' });

    render(<PivotResultGrid result={result} isLoading={false} />);

    expect(screen.getByText('쿼리 실행 중 오류가 발생했습니다')).toBeDefined();
  });

  it('에러 상태에서 테이블을 표시하지 않는다', () => {
    const result = makeResult({ error: '에러 발생' });

    const { container } = render(<PivotResultGrid result={result} isLoading={false} />);

    expect(container.querySelector('table')).toBeNull();
  });
});

// ─── 정상 결과 렌더링 ────────────────────────────────────

describe('PivotResultGrid — 결과 테이블', () => {
  it('컬럼 헤더를 표시한다', () => {
    render(<PivotResultGrid result={makeResult()} isLoading={false} />);

    expect(screen.getByText('year')).toBeDefined();
    expect(screen.getByText('revenue')).toBeDefined();
  });

  it('데이터 행을 표시한다', () => {
    render(<PivotResultGrid result={makeResult()} isLoading={false} />);

    expect(screen.getByText('2025')).toBeDefined();
    expect(screen.getByText('100000')).toBeDefined();
    expect(screen.getByText('2026')).toBeDefined();
    expect(screen.getByText('150000')).toBeDefined();
  });

  it('행 수 통계를 표시한다', () => {
    render(<PivotResultGrid result={makeResult()} isLoading={false} />);

    // "2행" 텍스트 확인
    expect(screen.getByText('2행')).toBeDefined();
  });

  it('실행 시간 통계를 표시한다', () => {
    render(<PivotResultGrid result={makeResult()} isLoading={false} />);

    expect(screen.getByText('42ms')).toBeDefined();
  });

  it('NULL 셀에 이탤릭 NULL 텍스트를 표시한다', () => {
    const result = makeResult({
      rows: [['2025', null]],
      row_count: 1,
    });

    render(<PivotResultGrid result={result} isLoading={false} />);

    expect(screen.getByText('NULL')).toBeDefined();
  });
});

// ─── 빈 결과 ──────────────────────────────────────────────

describe('PivotResultGrid — 빈 결과', () => {
  it('결과가 0행이면 "결과가 없습니다" 메시지를 표시한다', () => {
    const result = makeResult({
      columns: ['year'],
      rows: [],
      row_count: 0,
    });

    render(<PivotResultGrid result={result} isLoading={false} />);

    expect(screen.getByText('결과가 없습니다')).toBeDefined();
  });
});
