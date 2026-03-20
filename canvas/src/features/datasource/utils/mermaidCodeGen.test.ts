import { describe, it, expect } from 'vitest';
import { generateMermaidERCode, getConnectedTables } from './mermaidCodeGen';
import type { ERDTableInfo, ERDColumnInfo } from '../types/erd';

// ---------------------------------------------------------------------------
// 헬퍼: 테스트용 컬럼/테이블 빌더
// ---------------------------------------------------------------------------

function col(
  name: string,
  dataType = 'varchar',
  opts: Partial<ERDColumnInfo> = {},
): ERDColumnInfo {
  return {
    name,
    dataType,
    isPrimaryKey: false,
    isForeignKey: false,
    nullable: true,
    ...opts,
  };
}

function table(name: string, columns: ERDColumnInfo[], schema = 'public'): ERDTableInfo {
  return { name, schema, columns };
}

// ---------------------------------------------------------------------------
// generateMermaidERCode
// ---------------------------------------------------------------------------

describe('generateMermaidERCode', () => {
  it('빈 입력 → 빈 코드와 통계 0 반환', () => {
    const result = generateMermaidERCode([]);
    expect(result.code).toBe('');
    expect(result.stats).toEqual({ tables: 0, relationships: 0, columns: 0 });
    expect(result.relations).toEqual([]);
  });

  it('기본 테이블 → 올바른 Mermaid erDiagram 코드 생성', () => {
    const tables = [
      table('orders', [
        col('id', 'integer', { isPrimaryKey: true }),
        col('amount', 'decimal'),
        col('status', 'varchar'),
      ]),
    ];

    const result = generateMermaidERCode(tables);

    expect(result.code).toContain('erDiagram');
    expect(result.code).toContain('orders {');
    expect(result.code).toContain('int id PK');
    expect(result.code).toContain('float amount');
    expect(result.code).toContain('string status');
    expect(result.stats.tables).toBe(1);
    expect(result.stats.columns).toBe(3);
  });

  it('PK 표시: id 컬럼에 PK 마커 포함', () => {
    const tables = [
      table('users', [col('id', 'serial', { isPrimaryKey: true })]),
    ];

    const result = generateMermaidERCode(tables);
    expect(result.code).toContain('int id PK');
  });

  it('FK 추론: customer_id → customers 테이블 참조', () => {
    const tables = [
      table('orders', [
        col('id', 'int', { isPrimaryKey: true }),
        col('customer_id', 'int'),
      ]),
      table('customers', [
        col('id', 'int', { isPrimaryKey: true }),
        col('name', 'varchar'),
      ]),
    ];

    const result = generateMermaidERCode(tables);

    // FK 마커가 생성되어야 함
    expect(result.code).toContain('int customer_id FK');
    // 관계 라인이 생성되어야 함
    expect(result.code).toContain('orders }o--|| customers');
    expect(result.stats.relationships).toBe(1);
  });

  it('FK 추론: 복수형 테이블(processes) 매칭 — process_id → processes', () => {
    const tables = [
      table('tasks', [
        col('id', 'int', { isPrimaryKey: true }),
        col('process_id', 'int'),
      ]),
      table('processes', [col('id', 'int', { isPrimaryKey: true })]),
    ];

    const result = generateMermaidERCode(tables);
    expect(result.relations).toHaveLength(1);
    expect(result.relations[0].toTable).toBe('processes');
  });

  it('PK 컬럼은 FK로 추론하지 않음', () => {
    // order_id가 PK인 경우 → FK 추론 스킵
    const tables = [
      table('order_items', [
        col('order_id', 'int', { isPrimaryKey: true }),
      ]),
      table('orders', [col('id', 'int', { isPrimaryKey: true })]),
    ];

    const result = generateMermaidERCode(tables);
    expect(result.relations).toHaveLength(0);
  });

  it('특수문자 테이블명 sanitize: "my-table.v2" → "my_table_v2"', () => {
    const tables = [
      table('my-table.v2', [col('id', 'int', { isPrimaryKey: true })]),
    ];

    const result = generateMermaidERCode(tables);
    expect(result.code).toContain('my_table_v2 {');
    // 원본 특수문자가 남아있으면 안 됨
    expect(result.code).not.toContain('my-table.v2');
  });

  it('maxColumnsPerTable 옵션: 컬럼 수 제한 및 생략 표시', () => {
    const columns = Array.from({ length: 12 }, (_, i) =>
      col(`col_${i}`, 'varchar'),
    );
    const tables = [table('wide_table', columns)];

    const result = generateMermaidERCode(tables, { maxColumnsPerTable: 5 });

    // 5개 컬럼만 표시되고 나머지 7개는 생략 표시
    expect(result.code).toContain('_more_7_cols');
    // 통계의 columns는 전체 컬럼 수
    expect(result.stats.columns).toBe(12);
  });

  it('데이터 타입 정규화: boolean, timestamp, json, uuid, bytea', () => {
    const tables = [
      table('typed', [
        col('active', 'boolean'),
        col('created_at', 'timestamp with time zone'),
        col('payload', 'jsonb'),
        col('ref', 'uuid'),
        col('data', 'bytea'),
      ]),
    ];

    const result = generateMermaidERCode(tables);
    expect(result.code).toContain('boolean active');
    expect(result.code).toContain('datetime created_at');
    expect(result.code).toContain('json payload');
    expect(result.code).toContain('uuid ref');
    expect(result.code).toContain('binary data');
  });

  it('이미 FK 플래그가 설정된 컬럼은 재추론하지 않음', () => {
    const tables = [
      table('orders', [
        col('id', 'int', { isPrimaryKey: true }),
        col('user_id', 'int', { isForeignKey: true, referencedTable: 'accounts' }),
      ]),
      table('users', [col('id', 'int', { isPrimaryKey: true })]),
      table('accounts', [col('id', 'int', { isPrimaryKey: true })]),
    ];

    const result = generateMermaidERCode(tables);
    // user_id는 이미 accounts를 참조하므로 users로 재추론하지 않아야 함
    expect(result.relations[0].toTable).toBe('accounts');
  });
});

// ---------------------------------------------------------------------------
// getConnectedTables
// ---------------------------------------------------------------------------

describe('getConnectedTables', () => {
  it('시드 테이블에서 FK로 연결된 테이블만 반환', () => {
    const allTables = [
      table('orders', [
        col('id', 'int', { isPrimaryKey: true }),
        col('customer_id', 'int', { isForeignKey: true, referencedTable: 'customers' }),
      ]),
      table('customers', [col('id', 'int', { isPrimaryKey: true })]),
      table('products', [col('id', 'int', { isPrimaryKey: true })]),
    ];

    const result = getConnectedTables([allTables[0]], allTables);

    const names = result.map((t) => t.name);
    expect(names).toContain('orders');
    expect(names).toContain('customers');
    // products는 연결되지 않음
    expect(names).not.toContain('products');
  });

  it('BFS 탐색: 체인 관계 (A→B→C) 를 모두 반환', () => {
    const allTables = [
      table('a', [
        col('id', 'int', { isPrimaryKey: true }),
        col('b_id', 'int', { isForeignKey: true, referencedTable: 'b' }),
      ]),
      table('b', [
        col('id', 'int', { isPrimaryKey: true }),
        col('c_id', 'int', { isForeignKey: true, referencedTable: 'c' }),
      ]),
      table('c', [col('id', 'int', { isPrimaryKey: true })]),
      table('isolated', [col('id', 'int', { isPrimaryKey: true })]),
    ];

    const result = getConnectedTables([allTables[0]], allTables);
    const names = result.map((t) => t.name);

    expect(names).toContain('a');
    expect(names).toContain('b');
    expect(names).toContain('c');
    expect(names).not.toContain('isolated');
  });

  it('역참조 포함: 다른 테이블이 시드 테이블을 참조하는 경우', () => {
    const allTables = [
      table('users', [col('id', 'int', { isPrimaryKey: true })]),
      table('posts', [
        col('id', 'int', { isPrimaryKey: true }),
        col('user_id', 'int', { isForeignKey: true, referencedTable: 'users' }),
      ]),
    ];

    // 시드가 users이면, posts가 users를 역참조하므로 포함
    const result = getConnectedTables([allTables[0]], allTables);
    const names = result.map((t) => t.name);
    expect(names).toContain('users');
    expect(names).toContain('posts');
  });

  it('단절 그래프: 연결 없는 테이블은 제외', () => {
    const allTables = [
      table('island_a', [col('id', 'int', { isPrimaryKey: true })]),
      table('island_b', [col('id', 'int', { isPrimaryKey: true })]),
    ];

    const result = getConnectedTables([allTables[0]], allTables);
    const names = result.map((t) => t.name);
    expect(names).toContain('island_a');
    expect(names).not.toContain('island_b');
  });
});
