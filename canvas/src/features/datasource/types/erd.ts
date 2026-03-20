/**
 * ERD(Entity-Relationship Diagram) 시각화 관련 타입 정의.
 * Oracle Meta API의 TableMeta/ColumnMeta를 ERD 렌더링용으로 변환한 모델.
 */

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
