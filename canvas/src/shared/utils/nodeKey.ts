/**
 * nodeKey 유틸리티 — 프론트엔드/백엔드 공통 테이블 식별자
 *
 * 형식: ${mode}:${datasource}:${schema}:${table}
 * 예시: text2sql:robo_postgres:public:ORDERS
 */

/** 스키마 데이터 소스 모드 */
export type SchemaMode = 'robo' | 'text2sql';

/** nodeKey를 생성한다 */
export function buildNodeKey(
  mode: SchemaMode,
  datasource: string,
  schema: string,
  tableName: string,
): string {
  return `${mode}:${datasource || ''}:${schema || 'public'}:${tableName}`;
}

/** nodeKey를 파싱한다. 테이블명에 콜론이 포함되어 있어도 안전하게 처리한다. */
export function parseNodeKey(nodeKey: string): {
  mode: SchemaMode;
  datasource: string;
  schema: string;
  tableName: string;
} {
  const parts = nodeKey.split(':');
  const mode = (parts[0] as SchemaMode) || 'text2sql';
  const datasource = parts[1] || '';
  const schema = parts[2] || 'public';
  // 세 번째 콜론 이후 전부가 테이블명 (콜론이 포함될 수 있음)
  const tableName = parts.slice(3).join(':') || '';
  return { mode, datasource, schema, tableName };
}
