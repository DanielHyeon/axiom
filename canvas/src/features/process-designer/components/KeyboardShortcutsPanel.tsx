// features/process-designer/components/KeyboardShortcutsPanel.tsx
// 키보드 단축키 도움말 패널 (설계 §10.2 — Shift+?)

import { useTranslation } from 'react-i18next';

interface KeyboardShortcutsPanelProps {
 open: boolean;
 onClose: () => void;
}

const SHORTCUT_GROUPS = [
 {
 titleKey: 'processDesignerExt.shortcuts.navigation',
 shortcuts: [
 { key: 'Tab', descKey: 'processDesignerExt.shortcuts.nextNode' },
 { key: 'Shift+Tab', descKey: 'processDesignerExt.shortcuts.prevNode' },
 { key: 'Enter', descKey: 'processDesignerExt.shortcuts.selectFocused' },
 { key: '+ / -', descKey: 'processDesignerExt.shortcuts.zoomInOut' },
 { key: 'Ctrl+Arrow', descKey: 'processDesignerExt.shortcuts.canvasPanning' },
 ],
 },
 {
 titleKey: 'processDesignerExt.shortcuts.editing',
 shortcuts: [
 { key: 'Arrow Keys', descKey: 'processDesignerExt.shortcuts.moveNode' },
 { key: 'Shift+Arrow', descKey: 'processDesignerExt.shortcuts.preciseMove' },
 { key: 'Delete', descKey: 'processDesignerExt.shortcuts.deleteSelection' },
 { key: 'Ctrl+D', descKey: 'processDesignerExt.shortcuts.duplicateNode' },
 { key: 'Ctrl+A', descKey: 'processDesignerExt.shortcuts.selectAll' },
 { key: 'Ctrl+Z', descKey: 'processDesignerExt.shortcuts.undo' },
 { key: 'Ctrl+Shift+Z', descKey: 'processDesignerExt.shortcuts.redo' },
 ],
 },
 {
 titleKey: 'processDesignerExt.shortcuts.toolSwitch',
 shortcuts: [
 { key: 'V', descKey: 'processDesignerExt.shortcuts.selectMode' },
 { key: 'C', descKey: 'processDesignerExt.shortcuts.connectionMode' },
 { key: 'Escape', descKey: 'processDesignerExt.shortcuts.cancelMode' },
 ],
 },
 {
 titleKey: 'processDesignerExt.shortcuts.addNode',
 shortcuts: [
 { key: 'B', descKey: 'processDesignerExt.shortcuts.actionNode' },
 { key: 'E', descKey: 'processDesignerExt.shortcuts.eventNode' },
 { key: 'N', descKey: 'processDesignerExt.shortcuts.entityNode' },
 { key: 'R', descKey: 'processDesignerExt.shortcuts.ruleNode' },
 { key: 'S', descKey: 'processDesignerExt.shortcuts.stakeholderNode' },
 { key: 'T', descKey: 'processDesignerExt.shortcuts.reportNode' },
 { key: 'M', descKey: 'processDesignerExt.shortcuts.measureNode' },
 { key: 'D', descKey: 'processDesignerExt.shortcuts.domainNode' },
 ],
 },
] as const;

export function KeyboardShortcutsPanel({ open, onClose }: KeyboardShortcutsPanelProps) {
 const { t } = useTranslation();
 if (!open) return null;

 return (
 <div className="fixed inset-0 z-50 flex items-center justify-center bg-sidebar/60">
 <div
 className="bg-card border border-border rounded-lg w-[520px] max-h-[80vh] overflow-auto shadow-xl"
 role="dialog"
 aria-label={t('processDesignerExt.shortcuts.title')}
 >
 <div className="flex items-center justify-between px-5 py-4 border-b border-border">
 <h2 className="text-sm font-semibold text-foreground">{t('processDesignerExt.shortcuts.title')}</h2>
 <button
 type="button"
 onClick={onClose}
 className="text-foreground0 hover:text-foreground/80 text-lg leading-none"
 aria-label={t('common.close')}
 >
 &times;
 </button>
 </div>

 <div className="p-5 space-y-5">
 {SHORTCUT_GROUPS.map((group) => (
 <section key={group.titleKey}>
 <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground0 mb-2">
 {t(group.titleKey)}
 </h3>
 <div className="space-y-1">
 {group.shortcuts.map((s) => (
 <div key={s.key} className="flex items-center justify-between text-xs py-1">
 <span className="text-foreground/80">{t(s.descKey)}</span>
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
 {t('processDesignerExt.shortcuts.closeBtn')} (Escape)
 </button>
 </div>
 </div>
 </div>
 );
}
