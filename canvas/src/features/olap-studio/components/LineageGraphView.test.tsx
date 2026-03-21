/**
 * LineageGraphView 컴포넌트 테스트.
 *
 * Mermaid 리니지 그래프 렌더링 로직을 검증한다.
 * 엔티티/엣지 조합에 따른 Mermaid 코드 생성, 빈 상태 처리,
 * 타입별 색상·형태·라벨 매핑을 테스트한다.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LineageGraphView } from './LineageGraphView';
import type { LineageEntity, LineageEdge } from './LineageGraphView';

// MermaidERDRenderer 모킹 — mermaidCode를 그대로 표시
vi.mock('@/shared/components/MermaidERDRenderer', () => ({
  MermaidERDRenderer: ({ mermaidCode }: { mermaidCode: string }) => (
    <pre data-testid="mermaid-code">{mermaidCode}</pre>
  ),
}));

// ─── 테스트 데이터 ──────────────────────────────────────────

const sampleEntities: LineageEntity[] = [
  { id: 'e1', entity_type: 'SOURCE_TABLE', display_name: 'raw_orders' },
  { id: 'e2', entity_type: 'FACT', display_name: 'fact_sales' },
  { id: 'e3', entity_type: 'DIMENSION', display_name: 'dim_product' },
];

const sampleEdges: LineageEdge[] = [
  { from_entity_id: 'e1', to_entity_id: 'e2', edge_type: 'LOADS_TO' },
  { from_entity_id: 'e3', to_entity_id: 'e2', edge_type: 'FEEDS' },
];

// ─── 유틸 ───────────────────────────────────────────────────

/** 렌더링 후 생성된 Mermaid 코드 문자열을 반환한다 */
function getMermaidCode(): string {
  return screen.getByTestId('mermaid-code').textContent || '';
}

// ─── 테스트 ─────────────────────────────────────────────────

describe('LineageGraphView', () => {
  // ── 빈 상태 ──────────────────────────────────────────────

  it('빈 엔티티: 빈 상태 메시지를 표시한다', () => {
    render(<LineageGraphView entities={[]} edges={[]} />);
    expect(screen.getByText('리니지 데이터가 없습니다')).toBeDefined();
  });

  it('빈 엔티티일 때 Mermaid 렌더러가 표시되지 않는다', () => {
    render(<LineageGraphView entities={[]} edges={[]} />);
    expect(screen.queryByTestId('mermaid-code')).toBeNull();
  });

  // ── 기본 렌더링 ──────────────────────────────────────────

  it('엔티티가 있으면 flowchart LR 디렉티브로 시작하는 Mermaid 코드를 생성한다', () => {
    render(<LineageGraphView entities={sampleEntities} edges={sampleEdges} />);
    expect(getMermaidCode()).toContain('flowchart LR');
  });

  it('모든 엔티티 display_name이 Mermaid 코드에 포함된다', () => {
    render(<LineageGraphView entities={sampleEntities} edges={sampleEdges} />);
    const code = getMermaidCode();
    expect(code).toContain('raw_orders');
    expect(code).toContain('fact_sales');
    expect(code).toContain('dim_product');
  });

  // ── 엣지 라벨 매핑 ──────────────────────────────────────

  it('알려진 엣지 타입은 한국어 라벨로 변환된다', () => {
    render(<LineageGraphView entities={sampleEntities} edges={sampleEdges} />);
    const code = getMermaidCode();
    // LOADS_TO → 적재, FEEDS → 공급
    expect(code).toContain('적재');
    expect(code).toContain('공급');
  });

  it('알 수 없는 엣지 타입은 원문 그대로 라벨에 표시된다', () => {
    const customEdge: LineageEdge[] = [
      { from_entity_id: 'e1', to_entity_id: 'e2', edge_type: 'CUSTOM_RELATION' },
    ];
    render(<LineageGraphView entities={sampleEntities} edges={customEdge} />);
    expect(getMermaidCode()).toContain('CUSTOM_RELATION');
  });

  // ── 엔티티 타입별 스타일 ────────────────────────────────

  it('엔티티 타입별 색상 스타일이 Mermaid 코드에 포함된다', () => {
    render(<LineageGraphView entities={sampleEntities} edges={sampleEdges} />);
    const code = getMermaidCode();
    // SOURCE_TABLE → blue-400, FACT → emerald-400, DIMENSION → amber-400
    expect(code).toContain('fill:#60A5FA');
    expect(code).toContain('fill:#34D399');
    expect(code).toContain('fill:#FBBF24');
  });

  it('ENTITY_COLORS에 없는 타입은 색상 스타일이 생략된다', () => {
    const unknownEntity: LineageEntity[] = [
      { id: 'u1', entity_type: 'UNKNOWN_TYPE', display_name: 'test_node' },
    ];
    render(<LineageGraphView entities={unknownEntity} edges={[]} />);
    const code = getMermaidCode();
    expect(code).toContain('test_node');
    // 색상 스타일 라인 없음
    expect(code).not.toContain('fill:');
  });

  // ── 엣지 필터링 ─────────────────────────────────────────

  it('존재하지 않는 엔티티를 참조하는 엣지는 무시된다', () => {
    const badEdge: LineageEdge[] = [
      { from_entity_id: 'e1', to_entity_id: 'missing_id', edge_type: 'LOADS_TO' },
    ];
    render(<LineageGraphView entities={sampleEntities} edges={badEdge} />);
    const code = getMermaidCode();
    // 화살표 연결(-->)이 없어야 함
    expect(code).not.toContain('-->');
  });

  // ── 경계 조건 ───────────────────────────────────────────

  it('엔티티 1개, 엣지 0개도 정상 렌더링된다', () => {
    render(<LineageGraphView entities={[sampleEntities[0]]} edges={[]} />);
    const code = getMermaidCode();
    expect(code).toContain('flowchart LR');
    expect(code).toContain('raw_orders');
  });
});
