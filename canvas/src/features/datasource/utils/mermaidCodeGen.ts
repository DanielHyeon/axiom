/**
 * ERD 데이터를 Mermaid erDiagram 코드로 변환하는 순수 함수 모듈.
 * KAIR MermaidERView.vue의 generateMermaidER() 로직을 TypeScript로 포팅.
 */

import type { ERDTableInfo, ERDColumnInfo, ERDRelation, ERDStats } from '../types/erd';

/** 테이블명에서 Mermaid 호환 식별자로 정규화 (특수문자 → 언더스코어) */
function sanitizeTableName(name: string): string {
  return name.replace(/[^a-zA-Z0-9_]/g, '_');
}

/** DB 데이터 타입을 Mermaid 표시용 간략 타입으로 변환 */
function normalizeDataType(rawType: string): string {
  const t = rawType.toLowerCase();
  if (t.includes('int') || t === 'serial' || t === 'bigserial') return 'int';
  if (t.includes('float') || t.includes('double') || t.includes('decimal') || t.includes('numeric') || t.includes('real')) return 'float';
  if (t.includes('bool')) return 'boolean';
  if (t.includes('date') || t.includes('time') || t.includes('timestamp')) return 'datetime';
  if (t.includes('text') || t.includes('clob')) return 'text';
  if (t.includes('varchar') || t.includes('char') || t.includes('character')) return 'string';
  if (t.includes('json')) return 'json';
  if (t.includes('uuid')) return 'uuid';
  if (t.includes('bytea') || t.includes('blob')) return 'binary';
  return 'string';
}

/**
 * _id 접미사 기반 FK 추론.
 * 예: customer_id → customers 테이블 참조, order_id → orders 테이블 참조.
 * allTableNames에 해당 테이블이 존재하는 경우에만 FK로 판정.
 */
function inferForeignKey(
  column: ERDColumnInfo,
  allTableNames: Set<string>
): { isFk: boolean; referencedTable?: string } {
  // 이미 PK이면 FK 추론 스킵
  if (column.isPrimaryKey) return { isFk: false };

  const name = column.name.toLowerCase();
  if (!name.endsWith('_id')) return { isFk: false };

  // customer_id → customer → customers (복수형 시도)
  const baseName = name.slice(0, -3); // '_id' 제거
  const candidates = [
    baseName,                   // user
    baseName + 's',            // users
    baseName + 'es',           // processes
    baseName.replace(/ie$/, 'y'), // categories (역변환은 어려우나 기본 시도)
  ];

  for (const candidate of candidates) {
    if (allTableNames.has(candidate)) {
      return { isFk: true, referencedTable: candidate };
    }
  }

  // 테이블명이 복수형이 아닐 수 있으므로 baseName 자체가 테이블에 있으면 매핑
  return { isFk: false };
}

/**
 * FK 관계를 추출하고 Mermaid 관계 코드 라인 생성.
 * 관계 표기: }o--|| (many-to-one: 왼쪽 many, 오른쪽 one)
 */
function extractRelations(tables: ERDTableInfo[]): ERDRelation[] {
  const relations: ERDRelation[] = [];
  const seen = new Set<string>();

  for (const table of tables) {
    for (const col of table.columns) {
      if (col.isForeignKey && col.referencedTable) {
        const key = `${table.name}:${col.name}->${col.referencedTable}`;
        if (seen.has(key)) continue;
        seen.add(key);

        relations.push({
          fromTable: table.name,
          fromColumn: col.name,
          toTable: col.referencedTable,
          toColumn: 'id',
          type: 'many-to-one',
        });
      }
    }
  }

  return relations;
}

/** Mermaid 컬럼 라인 생성: "    int id PK" */
function formatColumnLine(col: ERDColumnInfo): string {
  const type = normalizeDataType(col.dataType);
  let marker = '';
  if (col.isPrimaryKey) marker = ' PK';
  else if (col.isForeignKey) marker = ' FK';
  return `        ${type} ${sanitizeTableName(col.name)}${marker}`;
}

/**
 * ERDTableInfo[] → Mermaid erDiagram 코드 + 통계 생성.
 *
 * @param tables - ERD 테이블 목록
 * @param options.maxColumnsPerTable - 테이블당 최대 표시 컬럼 수 (기본 8)
 * @returns { code: Mermaid 코드 문자열, stats: ERD 통계, relations: FK 관계 목록 }
 */
export function generateMermaidERCode(
  tables: ERDTableInfo[],
  options?: { maxColumnsPerTable?: number }
): { code: string; stats: ERDStats; relations: ERDRelation[] } {
  const maxCols = options?.maxColumnsPerTable ?? 8;

  if (tables.length === 0) {
    return { code: '', stats: { tables: 0, relationships: 0, columns: 0 }, relations: [] };
  }

  // FK 추론을 위한 전체 테이블명 집합
  const allTableNames = new Set(tables.map((t) => t.name.toLowerCase()));

  // FK 추론 적용
  const enrichedTables = tables.map((table) => ({
    ...table,
    columns: table.columns.map((col) => {
      if (col.isForeignKey) return col; // 이미 FK 플래그가 있으면 유지
      const fkResult = inferForeignKey(col, allTableNames);
      if (fkResult.isFk) {
        return { ...col, isForeignKey: true, referencedTable: fkResult.referencedTable };
      }
      return col;
    }),
  }));

  const relations = extractRelations(enrichedTables);
  let totalColumns = 0;

  const lines: string[] = ['erDiagram'];

  // 테이블 정의
  for (const table of enrichedTables) {
    const safeName = sanitizeTableName(table.name);
    lines.push(`    ${safeName} {`);

    const displayCols = table.columns.slice(0, maxCols);
    const remainingCount = table.columns.length - displayCols.length;
    totalColumns += table.columns.length;

    for (const col of displayCols) {
      lines.push(formatColumnLine(col));
    }

    // 생략된 컬럼 표시
    if (remainingCount > 0) {
      lines.push(`        string _more_${remainingCount}_cols ""`);
    }

    lines.push('    }');
  }

  // 관계 정의
  for (const rel of relations) {
    const from = sanitizeTableName(rel.fromTable);
    const to = sanitizeTableName(rel.toTable);
    // many-to-one: }o--|| (from이 many, to가 one)
    lines.push(`    ${from} }o--|| ${to} : "${rel.fromColumn}"`);
  }

  return {
    code: lines.join('\n'),
    stats: {
      tables: enrichedTables.length,
      relationships: relations.length,
      columns: totalColumns,
    },
    relations,
  };
}

/**
 * 시드 테이블에서 FK로 연결된 테이블만 추출 (연결된 테이블만 보기 모드).
 * BFS로 FK 관계를 따라가며 연결된 테이블을 수집.
 */
export function getConnectedTables(
  seedTables: ERDTableInfo[],
  allTables: ERDTableInfo[]
): ERDTableInfo[] {
  const allTableMap = new Map(allTables.map((t) => [t.name.toLowerCase(), t]));
  const visited = new Set<string>();
  const queue: string[] = seedTables.map((t) => t.name.toLowerCase());

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (visited.has(current)) continue;
    visited.add(current);

    const table = allTableMap.get(current);
    if (!table) continue;

    // FK 관계를 따라 연결된 테이블 탐색
    for (const col of table.columns) {
      if (col.isForeignKey && col.referencedTable) {
        const ref = col.referencedTable.toLowerCase();
        if (!visited.has(ref)) queue.push(ref);
      }
    }
  }

  // 역참조도 포함: 다른 테이블이 현재 visited 테이블을 참조하는 경우
  for (const table of allTables) {
    for (const col of table.columns) {
      if (col.isForeignKey && col.referencedTable) {
        if (visited.has(col.referencedTable.toLowerCase()) && !visited.has(table.name.toLowerCase())) {
          visited.add(table.name.toLowerCase());
        }
      }
    }
  }

  return allTables.filter((t) => visited.has(t.name.toLowerCase()));
}
