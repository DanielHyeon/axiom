// features/process-designer/components/KeyboardShortcutsPanel.tsx
// 키보드 단축키 도움말 패널 (설계 §10.2 — Shift+?)

interface KeyboardShortcutsPanelProps {
 open: boolean;
 onClose: () => void;
}

const SHORTCUT_GROUPS = [
 {
 title: '탐색',
 shortcuts: [
 { key: 'Tab', desc: '다음 노드로 포커스 이동' },
 { key: 'Shift+Tab', desc: '이전 노드로 포커스 이동' },
 { key: 'Enter', desc: '포커스된 노드 선택' },
 { key: '+ / -', desc: '줌 인 / 줌 아웃' },
 { key: 'Ctrl+Arrow', desc: '캔버스 패닝' },
 ],
 },
 {
 title: '편집',
 shortcuts: [
 { key: 'Arrow Keys', desc: '선택된 노드 이동 (10px)' },
 { key: 'Shift+Arrow', desc: '정밀 이동 (1px)' },
 { key: 'Delete', desc: '선택 항목 삭제' },
 { key: 'Ctrl+D', desc: '선택 노드 복제' },
 { key: 'Ctrl+A', desc: '전체 선택' },
 { key: 'Ctrl+Z', desc: '실행 취소' },
 { key: 'Ctrl+Shift+Z', desc: '다시 실행' },
 ],
 },
 {
 title: '도구 전환',
 shortcuts: [
 { key: 'V', desc: '선택 모드' },
 { key: 'C', desc: '연결선 모드' },
 { key: 'Escape', desc: '모드 취소 / 선택 해제' },
 ],
 },
 {
 title: '노드 추가',
 shortcuts: [
 { key: 'B', desc: 'Action (업무 행위)' },
 { key: 'E', desc: 'Event (업무 사건)' },
 { key: 'N', desc: 'Entity (업무 객체)' },
 { key: 'R', desc: 'Rule (업무 규칙)' },
 { key: 'S', desc: 'Stakeholder (이해관계자)' },
 { key: 'T', desc: 'Report (업무 보고서)' },
 { key: 'M', desc: 'Measure (KPI/측정값)' },
 { key: 'D', desc: 'Domain (부서/사업부)' },
 ],
 },
] as const;

export function KeyboardShortcutsPanel({ open, onClose }: KeyboardShortcutsPanelProps) {
 if (!open) return null;

 return (
 <div className="fixed inset-0 z-50 flex items-center justify-center bg-sidebar/60">
 <div
 className="bg-card border border-border rounded-lg w-[520px] max-h-[80vh] overflow-auto shadow-xl"
 role="dialog"
 aria-label="키보드 단축키 도움말"
 >
 <div className="flex items-center justify-between px-5 py-4 border-b border-border">
 <h2 className="text-sm font-semibold text-foreground">키보드 단축키</h2>
 <button
 type="button"
 onClick={onClose}
 className="text-foreground0 hover:text-foreground/80 text-lg leading-none"
 aria-label="닫기"
 >
 &times;
 </button>
 </div>

 <div className="p-5 space-y-5">
 {SHORTCUT_GROUPS.map((group) => (
 <section key={group.title}>
 <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground0 mb-2">
 {group.title}
 </h3>
 <div className="space-y-1">
 {group.shortcuts.map((s) => (
 <div key={s.key} className="flex items-center justify-between text-xs py-1">
 <span className="text-foreground/80">{s.desc}</span>
 <kbd className="bg-muted border border-border rounded px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
 {s.key}
 </kbd>
 </div>
 ))}
 </div>
 </section>
 ))}
 </div>

 <div className="px-5 py-3 border-t border-border text-right">
 <button
 type="button"
 onClick={onClose}
 className="text-xs text-muted-foreground hover:text-foreground"
 >
 닫기 (Escape)
 </button>
 </div>
 </div>
 </div>
 );
}
