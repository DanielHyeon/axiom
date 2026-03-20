/**
 * ERD(Entity-Relationship Diagram) 시각화 관련 타입 정의.
 *
 * 실제 타입은 shared/types/schema.ts에서 정의되며,
 * 이 파일은 하위 호환성을 위해 re-export만 수행한다.
 * datasource feature 내부에서 기존 import 경로를 그대로 쓸 수 있도록 유지한다.
 */

export type {
  ERDColumnInfo,
  ERDTableInfo,
  ERDRelation,
  ERDStats,
  ERDFilter,
} from '@/shared/types/schema';
