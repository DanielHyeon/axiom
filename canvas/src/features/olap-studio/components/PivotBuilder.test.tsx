/**
 * PivotBuilder 컴포넌트 테스트.
 *
 * 4개 드롭존(행, 열, 측정값, 필터) 렌더링과 필드 칩 표시,
 * 빈 상태 메시지, 제거 버튼 동작을 검증한다.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PivotBuilder } from './PivotBuilder';

// ─── 테스트 헬퍼 ──────────────────────────────────────────

/** 기본 props — 행 1개, 측정값 1개, 열/필터 비어있음 */
function makeDefaultProps(overrides = {}) {
  return {
    rows: [{ dimension: 'dim_date', level: 'year' }],
    columns: [],
    measures: [{ name: 'sales', aggregator: 'SUM' }],
    filters: [],
    onRemoveRow: vi.fn(),
    onRemoveColumn: vi.fn(),
    onRemoveMeasure: vi.fn(),
    onRemoveFilter: vi.fn(),
    ...overrides,
  };
}

// ─── 드롭존 렌더링 ────────────────────────────────────────

describe('PivotBuilder — 드롭존 렌더링', () => {
  it('4개 드롭존 라벨이 모두 표시된다', () => {
    render(<PivotBuilder {...makeDefaultProps()} />);

    expect(screen.getByText('행 (Rows)')).toBeDefined();
    expect(screen.getByText('열 (Columns)')).toBeDefined();
    expect(screen.getByText('측정값 (Measures)')).toBeDefined();
    expect(screen.getByText('필터 (Filters)')).toBeDefined();
  });

  it('행 필드를 dimension.level 형식의 칩으로 표시한다', () => {
    render(<PivotBuilder {...makeDefaultProps()} />);

    expect(screen.getByText('dim_date.year')).toBeDefined();
  });

  it('측정값을 AGGREGATOR(name) 형식의 칩으로 표시한다', () => {
    render(<PivotBuilder {...makeDefaultProps()} />);

    expect(screen.getByText('SUM(sales)')).toBeDefined();
  });

  it('빈 드롭존에 "필드를 추가하세요" 안내 메시지를 표시한다', () => {
    render(<PivotBuilder {...makeDefaultProps()} />);

    // 열과 필터가 비어있으므로 안내 메시지 2개
    const emptyMessages = screen.getAllByText('필드를 추가하세요');
    expect(emptyMessages.length).toBe(2);
  });

  it('모든 영역에 필드가 있으면 안내 메시지가 없다', () => {
    const props = makeDefaultProps({
      columns: [{ dimension: 'dim_product', level: 'category' }],
      filters: [{ dimension: 'dim_region', level: 'country', operator: '=', value: 'Korea' }],
    });

    render(<PivotBuilder {...props} />);

    expect(screen.queryByText('필드를 추가하세요')).toBeNull();
  });
});

// ─── 필드 칩 다양한 데이터 ────────────────────────────────

describe('PivotBuilder — 다양한 데이터 렌더링', () => {
  it('여러 행 필드를 모두 칩으로 표시한다', () => {
    const props = makeDefaultProps({
      rows: [
        { dimension: 'dim_date', level: 'year' },
        { dimension: 'dim_date', level: 'quarter' },
        { dimension: 'dim_product', level: 'category' },
      ],
    });

    render(<PivotBuilder {...props} />);

    expect(screen.getByText('dim_date.year')).toBeDefined();
    expect(screen.getByText('dim_date.quarter')).toBeDefined();
    expect(screen.getByText('dim_product.category')).toBeDefined();
  });

  it('여러 측정값을 각각 집계 함수와 함께 표시한다', () => {
    const props = makeDefaultProps({
      measures: [
        { name: 'sales', aggregator: 'SUM' },
        { name: 'quantity', aggregator: 'AVG' },
        { name: 'orders', aggregator: 'COUNT' },
      ],
    });

    render(<PivotBuilder {...props} />);

    expect(screen.getByText('SUM(sales)')).toBeDefined();
    expect(screen.getByText('AVG(quantity)')).toBeDefined();
    expect(screen.getByText('COUNT(orders)')).toBeDefined();
  });

  it('필터 칩에 dimension.level operator value 형식으로 표시한다', () => {
    const props = makeDefaultProps({
      filters: [
        { dimension: 'dim_region', level: 'country', operator: '=', value: 'Korea' },
      ],
    });

    render(<PivotBuilder {...props} />);

    expect(screen.getByText('dim_region.country = Korea')).toBeDefined();
  });

  it('IN 필터에 리스트 값을 콤마로 결합하여 표시한다', () => {
    const props = makeDefaultProps({
      filters: [
        { dimension: 'dim_region', level: 'country', operator: 'IN', value: ['Korea', 'Japan'] },
      ],
    });

    render(<PivotBuilder {...props} />);

    expect(screen.getByText('dim_region.country IN Korea,Japan')).toBeDefined();
  });
});

// ─── 제거 버튼 동작 ───────────────────────────────────────

describe('PivotBuilder — 제거 버튼', () => {
  it('행 칩의 X 버튼 클릭 시 onRemoveRow를 인덱스와 함께 호출한다', () => {
    const onRemoveRow = vi.fn();
    const props = makeDefaultProps({ onRemoveRow });

    render(<PivotBuilder {...props} />);

    // aria-label로 제거 버튼 찾기
    const removeBtn = screen.getByLabelText('dim_date.year 제거');
    fireEvent.click(removeBtn);

    expect(onRemoveRow).toHaveBeenCalledOnce();
    expect(onRemoveRow).toHaveBeenCalledWith(0);
  });

  it('측정값 칩의 X 버튼 클릭 시 onRemoveMeasure를 호출한다', () => {
    const onRemoveMeasure = vi.fn();
    const props = makeDefaultProps({ onRemoveMeasure });

    render(<PivotBuilder {...props} />);

    const removeBtn = screen.getByLabelText('SUM(sales) 제거');
    fireEvent.click(removeBtn);

    expect(onRemoveMeasure).toHaveBeenCalledOnce();
    expect(onRemoveMeasure).toHaveBeenCalledWith(0);
  });

  it('여러 행 중 두 번째 칩 제거 시 인덱스 1이 전달된다', () => {
    const onRemoveRow = vi.fn();
    const props = makeDefaultProps({
      rows: [
        { dimension: 'dim_date', level: 'year' },
        { dimension: 'dim_date', level: 'month' },
      ],
      onRemoveRow,
    });

    render(<PivotBuilder {...props} />);

    const removeBtn = screen.getByLabelText('dim_date.month 제거');
    fireEvent.click(removeBtn);

    expect(onRemoveRow).toHaveBeenCalledWith(1);
  });
});

// ─── 필드 카운트 배지 ──────────────────────────────────────

describe('PivotBuilder — 카운트 배지', () => {
  it('필드가 있는 영역에는 카운트를 표시한다', () => {
    const props = makeDefaultProps({
      rows: [
        { dimension: 'a', level: 'b' },
        { dimension: 'c', level: 'd' },
      ],
    });

    render(<PivotBuilder {...props} />);

    // 행 영역에 "2" 카운트
    // 측정값 영역에 "1" 카운트
    // 텍스트 콘텐츠로 확인
    const container = document.body;
    expect(container.textContent).toContain('2');
    expect(container.textContent).toContain('1');
  });
});
