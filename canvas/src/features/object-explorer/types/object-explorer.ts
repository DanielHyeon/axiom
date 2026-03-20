/**
 * 오브젝트 탐색기 — TypeScript 타입 정의
 *
 * KAIR ObjectExplorerTab의 데이터 모델을 Axiom 패턴으로 재설계.
 * 도메인 feature의 ObjectType을 재사용하되, 인스턴스 탐색용 타입을 추가 정의.
 */

// ObjectType은 shared 레이어에서 가져온다 (feature 간 의존 제거)
import type { ObjectType } from '@/shared/types/domain';

// ──────────────────────────────────────
// 오브젝트 인스턴스
// ──────────────────────────────────────

/** 오브젝트 인스턴스 (ObjectType의 실제 데이터 행) */
export interface ObjectInstance {
  id: string;
  objectTypeId: string;
  objectTypeName: string;
  displayName: string;
  /** 동적 필드 값 (컬럼명 → 값) */
  fields: Record<string, unknown>;
  /** 1-hop 관련 인스턴스 목록 */
  relatedInstances: RelatedInstance[];
  created_at: string;
}

/** 관련 인스턴스 (그래프 엣지 대상) */
export interface RelatedInstance {
  instanceId: string;
  objectTypeName: string;
  displayName: string;
  relationName: string;
  relationType: string;
}

// ──────────────────────────────────────
// 필터/페이지네이션
// ──────────────────────────────────────

/** 인스턴스 목록 필터 */
export interface InstanceFilter {
  search: string;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  page: number;
  pageSize: number;
}

/** 인스턴스 목록 API 응답 */
export interface InstanceListResponse {
  instances: ObjectInstance[];
  total: number;
  page: number;
  pageSize: number;
}

/** 인스턴스 상세 API 응답 */
export interface InstanceDetailResponse {
  instance: ObjectInstance;
}

// ──────────────────────────────────────
// 그래프 시각화용
// ──────────────────────────────────────

/** 그래프 노드 (Cytoscape용) */
export interface ExplorerGraphNode {
  id: string;
  label: string;
  objectTypeName: string;
  fields: Record<string, unknown>;
}

/** 그래프 엣지 (Cytoscape용) */
export interface ExplorerGraphEdge {
  source: string;
  target: string;
  label: string;
}

/** 그래프 데이터 번들 */
export interface ExplorerGraphData {
  nodes: ExplorerGraphNode[];
  edges: ExplorerGraphEdge[];
}

// ──────────────────────────────────────
// 좌측 패널 탭
// ──────────────────────────────────────

export type LeftPanelTab = 'search' | 'detail';

// ──────────────────────────────────────
// re-export (도메인 타입 재사용)
// ──────────────────────────────────────

export type { ObjectType };
