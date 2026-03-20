/**
 * 캔버스 데이터 스토어 — Zustand 슬라이스 통합
 *
 * 캔버스 데이터(items, connections) 관리 레이어.
 * Yjs CRDT 백엔드를 사용하며, WS 서버가 없으면 IndexedDB 로컬 전용 모드.
 *
 * 슬라이스 구조:
 * - itemSlice: 아이템(노드) CRUD
 * - connectionSlice: 연결선 CRUD
 * - boardSlice: 보드 로드/저장, Undo/Redo, 실시간 협업
 *
 * 기존 소비자(ProcessCanvas, hooks 등)에 변경 없이 동작.
 */

import { create } from 'zustand';
import { createItemSlice } from './slices/itemSlice';
import { createConnectionSlice } from './slices/connectionSlice';
import { createBoardSlice } from './slices/boardSlice';
import type { ItemSlice } from './slices/itemSlice';
import type { ConnectionSlice } from './slices/connectionSlice';
import type { BoardSlice } from './slices/boardSlice';

// ── Collaborator 타입 re-export (하위 호환) ──
export type { Collaborator } from './slices/boardSlice';

// ── 통합 스토어 타입 ──
type CanvasDataState = ItemSlice & ConnectionSlice & BoardSlice;

// ── 슬라이스 결합 스토어 생성 ──
export const useCanvasDataStore = create<CanvasDataState>()((...args) => ({
  ...createItemSlice(...args),
  ...createConnectionSlice(...args),
  ...createBoardSlice(...args),
}));
