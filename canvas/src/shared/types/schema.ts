/**
 * 스키마 관련 공통 타입 정의
 *
 * 여러 feature(datasource, nl2sql, ingestion 등)에서 공통으로 사용하는
 * 데이터소스, 테이블, 컬럼 메타데이터 타입을 모아 놓은 파일이다.
 * 특정 feature에 종속되지 않는 "공유 타입"이므로 shared/types에 위치한다.
 */

// ──────────────────────────────────────
// 데이터소스 정보
// ──────────────────────────────────────

/** Oracle Meta API — 데이터소스 기본 정보 */
export interface DatasourceInfo {
  id: string;
  name: string;
  type: string;
  host: string;
  database: string;
  schema: string;
  status: string;
}

// ──────────────────────────────────────
// 테이블 메타데이터
// ──────────────────────────────────────

/** Oracle Meta API — 테이블 한 개의 메타데이터 */
export interface TableMeta {
  name: string;
  schema: string;
  db: string;
  description: string | null;
  column_count: number;
  is_valid: boolean;
  has_vector: boolean;
}

// ──────────────────────────────────────
// 컬럼 메타데이터
// ──────────────────────────────────────

/** Oracle Meta API — 컬럼 한 개의 메타데이터 */
export interface ColumnMeta {
  name: string;
  fqn: string;
  data_type: string;
  nullable: boolean;
  is_primary_key: boolean;
  description: string | null;
  has_vector: boolean;
}

// ──────────────────────────────────────
// ERD(Entity-Relationship Diagram) 타입
// ──────────────────────────────────────

/** ERD에 표시할 컬럼 정보 */
export interface ERDColumnInfo {
  name: string;
  dataType: string;        // 정규화된 타입 (int, varchar, boolean 등)
  isPrimaryKey: boolean;
  isForeignKey: boolean;   // _id 접미사 기반 추론
  referencedTable?: string; // FK가 참조하는 테이블명
  nullable: boolean;
}

/** ERD에 표시할 테이블 정보 */
export interface ERDTableInfo {
  name: string;
  schema: string;
  description?: string;
  columns: ERDColumnInfo[];
}

/** FK 관계 정보 */
export interface ERDRelation {
  fromTable: string;
  fromColumn: string;
  toTable: string;
  toColumn: string;
  type: 'one-to-many' | 'many-to-one' | 'one-to-one';
}

/** ERD 통계 */
export interface ERDStats {
  tables: number;
  relationships: number;
  columns: number;
}

/** ERD 필터 옵션 */
export interface ERDFilter {
  searchQuery: string;
  showConnectedOnly: boolean;
  maxTables: number;
}
