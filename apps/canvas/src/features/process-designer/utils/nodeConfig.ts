// features/process-designer/utils/nodeConfig.ts
// 노드 타입별 메타데이터 SSOT — 색상, 단축키, 기본 크기 (설계 §2.1, §8)

import type { CanvasItemType, ConnectionType } from '../types/processDesigner';

export interface NodeTypeConfig {
  type: CanvasItemType;
  label: string;
  labelKo: string;
  color: string;
  shortcut: string | null;
  defaultWidth: number;
  defaultHeight: number;
  category: 'basic' | 'extended';
}

/** 11종 노드 설정 (설계 §2.1 + §2.2) */
export const NODE_CONFIGS: Record<CanvasItemType, NodeTypeConfig> = {
  contextBox:         { type: 'contextBox',         label: 'Domain',      labelKo: '부서/사업부',  color: '#e9ecef', shortcut: 'D', defaultWidth: 400, defaultHeight: 300, category: 'basic' },
  businessAction:     { type: 'businessAction',     label: 'Action',      labelKo: '업무 행위',    color: '#87ceeb', shortcut: 'B', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  businessEvent:      { type: 'businessEvent',      label: 'Event',       labelKo: '업무 사건',    color: '#ffb703', shortcut: 'E', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  businessEntity:     { type: 'businessEntity',     label: 'Entity',      labelKo: '업무 객체',    color: '#ffff99', shortcut: 'N', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  businessRule:       { type: 'businessRule',       label: 'Rule',        labelKo: '업무 규칙',    color: '#ffc0cb', shortcut: 'R', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  stakeholder:        { type: 'stakeholder',        label: 'Stakeholder', labelKo: '이해관계자',   color: '#d0f4de', shortcut: 'S', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  businessReport:     { type: 'businessReport',     label: 'Report',      labelKo: '업무 보고서',  color: '#90ee90', shortcut: 'T', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  measure:            { type: 'measure',            label: 'Measure',     labelKo: 'KPI/측정값',   color: '#9b59b6', shortcut: 'M', defaultWidth: 160, defaultHeight: 90,  category: 'basic' },
  eventLogBinding:    { type: 'eventLogBinding',    label: 'Log Binding', labelKo: '로그 바인딩',  color: '#607d8b', shortcut: null, defaultWidth: 140, defaultHeight: 80,  category: 'extended' },
  temporalAnnotation: { type: 'temporalAnnotation', label: 'Temporal',    labelKo: '시간 주석',    color: '#fce4ec', shortcut: null, defaultWidth: 140, defaultHeight: 60,  category: 'extended' },
};

/** 노드 타입 목록 (툴박스 표시 순서) */
export const BASIC_NODE_TYPES = Object.values(NODE_CONFIGS).filter(c => c.category === 'basic');
export const EXTENDED_NODE_TYPES = Object.values(NODE_CONFIGS).filter(c => c.category === 'extended');

/** 연결선 설정 (설계 §3.1) */
export const CONNECTION_CONFIGS: Record<ConnectionType, { stroke: string; dashArray?: string; label: string; labelKo: string }> = {
  triggers:  { stroke: '#3b82f6', label: 'triggers',  labelKo: '발생시킨다' },
  reacts_to: { stroke: '#ec4899', dashArray: '10,5', label: 'reacts to', labelKo: '반응한다' },
  produces:  { stroke: '#f97316', label: 'produces',  labelKo: '생성/변경한다' },
  binds_to:  { stroke: '#9ca3af', dashArray: '5,5', label: 'binds to', labelKo: '연결된다' },
};

/** 단축키 → 노드 타입 역매핑 (useCanvasKeyboard에서 사용) */
export const SHORTCUT_TO_TYPE: Record<string, CanvasItemType> = Object.fromEntries(
  Object.values(NODE_CONFIGS)
    .filter((c): c is NodeTypeConfig & { shortcut: string } => c.shortcut !== null)
    .map(c => [c.shortcut.toLowerCase(), c.type]),
) as Record<string, CanvasItemType>;
