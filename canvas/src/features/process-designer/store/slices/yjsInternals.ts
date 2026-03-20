/**
 * Yjs 내부 상태 관리 모듈
 *
 * Zustand 외부에서 Yjs 싱글턴 인스턴스를 관리한다.
 * Y.Doc, WebsocketProvider, IndexeddbPersistence, UndoManager 등의
 * 생명주기를 담당하며, 다른 슬라이스에서 참조하는 공유 변수를 제공.
 *
 * 외부에서 직접 변수를 재할당하는 사고를 방지하기 위해
 * getter/setter 함수로만 접근한다.
 */

import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { IndexeddbPersistence } from 'y-indexeddb';

// ── Yjs 싱글턴 인스턴스 (외부 직접 접근 불가) ──

let _ydoc: Y.Doc | null = null;
let _wsProvider: WebsocketProvider | null = null;
let _idbPersistence: IndexeddbPersistence | null = null;
let _undoManager: Y.UndoManager | null = null;
let _yItems: Y.Array<Y.Map<unknown>> | null = null;
let _yConnections: Y.Array<Y.Map<unknown>> | null = null;
let _localUserId = '';
let _localUserName = '';

// ── getter 함수: 읽기 전용 접근 ──

export function getYDoc() { return _ydoc; }
export function getWsProvider() { return _wsProvider; }
export function getIdbPersistence() { return _idbPersistence; }
export function getUndoManager() { return _undoManager; }
export function getYItems() { return _yItems; }
export function getYConnections() { return _yConnections; }
export function getLocalUserId() { return _localUserId; }
export function getLocalUserName() { return _localUserName; }

// ── setter 함수: 쓰기 접근 ──

export function setYDoc(doc: Y.Doc | null) { _ydoc = doc; }
export function setWsProvider(provider: WebsocketProvider | null) { _wsProvider = provider; }
export function setIdbPersistence(persistence: IndexeddbPersistence | null) { _idbPersistence = persistence; }
export function setUndoManager(manager: Y.UndoManager | null) { _undoManager = manager; }
export function setYItems(items: Y.Array<Y.Map<unknown>> | null) { _yItems = items; }
export function setYConnections(conns: Y.Array<Y.Map<unknown>> | null) { _yConnections = conns; }
export function setLocalUserId(id: string) { _localUserId = id; }
export function setLocalUserName(name: string) { _localUserName = name; }

// ── Yjs 인스턴스 정리 ──

/** 모든 Yjs 인스턴스를 파괴하고 null로 초기화 */
export function destroyYjs() {
  if (_undoManager) { _undoManager.destroy(); _undoManager = null; }
  if (_wsProvider) { _wsProvider.destroy(); _wsProvider = null; }
  if (_idbPersistence) { _idbPersistence.destroy(); _idbPersistence = null; }
  if (_ydoc) { _ydoc.destroy(); _ydoc = null; }
  _yItems = null;
  _yConnections = null;
}

// ── 유틸리티 함수 ──

/** Y.Array에서 id로 인덱스 검색 */
export function findIndexById(yArr: Y.Array<Y.Map<unknown>>, id: string): number {
  for (let i = 0; i < yArr.length; i++) {
    if (yArr.get(i).get('id') === id) return i;
  }
  return -1;
}

/** Y.Array 전체를 JSON으로 변환 */
export function yArrayToJSON<T>(yArr: Y.Array<Y.Map<unknown>>): T[] {
  return yArr.toJSON() as T[];
}

// ── WS 서버 URL ──

/** 환경 변수가 명시적으로 설정된 경우에만 WS 활성화 */
export const WS_URL = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_YJS_WS_URL)
  ? import.meta.env.VITE_YJS_WS_URL as string
  : null;

// ── 협업자 색상 팔레트 ──

const COLLAB_COLORS = [
  '#f87171', '#fb923c', '#facc15', '#4ade80',
  '#22d3ee', '#818cf8', '#c084fc', '#f472b6',
];

/** clientId 기반으로 색상 배정 */
export function assignColor(clientId: number): string {
  return COLLAB_COLORS[clientId % COLLAB_COLORS.length];
}
