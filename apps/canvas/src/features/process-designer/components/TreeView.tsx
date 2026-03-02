// @ts-nocheck
// features/process-designer/components/TreeView.tsx
// 트리/리스트 대체 뷰 — 캔버스와 병렬로 프로세스 모델을 트리 구조로 열람 (설계 §10.1)

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import type { CanvasItem, Connection } from '../types/processDesigner';
import { NODE_CONFIGS, CONNECTION_CONFIGS } from '../utils/nodeConfig';

interface TreeViewProps {
 items: CanvasItem[];
 connections: Connection[];
 selectedItemIds: string[];
 onSelectItem: (id: string) => void;
 onFocusCanvas: (id: string) => void;
}

interface TreeNode {
 item: CanvasItem;
 children: CanvasItem[];
 outgoing: { conn: Connection; target: CanvasItem }[];
 incoming: { conn: Connection; source: CanvasItem }[];
}

export function TreeView({ items, connections, selectedItemIds, onSelectItem, onFocusCanvas }: TreeViewProps) {
 const itemMap = useMemo(() => new Map(items.map((it) => [it.id, it])), [items]);

 // Build tree: contextBoxes → children, orphan nodes at root
 const tree = useMemo(() => {
 const contextBoxes = items.filter((it) => it.type === 'contextBox');
 const childrenOf = new Map<string, CanvasItem[]>();

 // Group items by parentContextBoxId
 for (const item of items) {
 if (item.type === 'contextBox') continue;
 const parentId = item.parentContextBoxId;
 if (parentId) {
 const arr = childrenOf.get(parentId) ?? [];
 arr.push(item);
 childrenOf.set(parentId, arr);
 }
 }

 // Orphan items (not contextBox, no parent)
 const orphans = items.filter(
 (it) => it.type !== 'contextBox' && !it.parentContextBoxId,
 );

 // Build connection lookup per item
 const outgoingMap = new Map<string, { conn: Connection; target: CanvasItem }[]>();
 const incomingMap = new Map<string, { conn: Connection; source: CanvasItem }[]>();

 for (const conn of connections) {
 const source = itemMap.get(conn.sourceId);
 const target = itemMap.get(conn.targetId);
 if (!source || !target) continue;

 const out = outgoingMap.get(conn.sourceId) ?? [];
 out.push({ conn, target });
 outgoingMap.set(conn.sourceId, out);

 const inc = incomingMap.get(conn.targetId) ?? [];
 inc.push({ conn, source });
 incomingMap.set(conn.targetId, inc);
 }

 const buildNode = (item: CanvasItem): TreeNode => ({
 item,
 children: childrenOf.get(item.id) ?? [],
 outgoing: outgoingMap.get(item.id) ?? [],
 incoming: incomingMap.get(item.id) ?? [],
 });

 return {
 domains: contextBoxes.map(buildNode),
 orphans: orphans.map(buildNode),
 };
 }, [items, connections, itemMap]);

 return (
 <div
 className="flex-1 overflow-auto text-sm"
 role="tree"
 aria-label="프로세스 모델 트리 뷰"
 >
 {tree.domains.map((domain) => (
 <DomainTreeItem
 key={domain.item.id}
 domain={domain}
 selectedItemIds={selectedItemIds}
 onSelectItem={onSelectItem}
 onFocusCanvas={onFocusCanvas}
 />
 ))}

 {tree.orphans.length > 0 && (
 <>
 {tree.domains.length > 0 && (
 <div className="mx-3 my-1 border-t border-border" />
 )}
 {tree.orphans.map((node) => (
 <NodeTreeItem
 key={node.item.id}
 node={node}
 depth={0}
 selectedItemIds={selectedItemIds}
 onSelectItem={onSelectItem}
 onFocusCanvas={onFocusCanvas}
 />
 ))}
 </>
 )}

 {items.length === 0 && (
 <div className="p-4 text-center text-foreground0 text-xs">
 캔버스에 노드를 추가하면 여기에 표시됩니다.
 </div>
 )}
 </div>
 );
}

// --- Domain (contextBox) tree item ---

function DomainTreeItem({
 domain,
 selectedItemIds,
 onSelectItem,
 onFocusCanvas,
}: {
 domain: TreeNode;
 selectedItemIds: string[];
 onSelectItem: (id: string) => void;
 onFocusCanvas: (id: string) => void;
}) {
 const [expanded, setExpanded] = useState(true);
 const selected = selectedItemIds.includes(domain.item.id);

 return (
 <div role="treeitem" aria-expanded={expanded} aria-label={`${domain.item.label} (Domain)`}>
 <button
 type="button"
 onClick={() => {
 onSelectItem(domain.item.id);
 setExpanded((v) => !v);
 }}
 onDoubleClick={() => onFocusCanvas(domain.item.id)}
 className={`
 w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs
 hover:bg-muted transition-colors
 ${selected ? 'bg-blue-900/30 text-primary/80' : 'text-foreground/80'}
 `}
 >
 <span className="text-foreground0">{expanded ? '▼' : '▸'}</span>
 <span
 className="w-2.5 h-2.5 rounded-sm shrink-0"
 style={{ backgroundColor: domain.item.color }}
 />
 <span className="truncate font-medium">{domain.item.label}</span>
 <span className="text-muted-foreground text-[10px] ml-auto shrink-0">Domain</span>
 </button>

 {expanded && (
 <div role="group">
 {domain.children.map((child) => (
 <NodeTreeItem
 key={child.id}
 node={{
 item: child,
 children: [],
 outgoing: domain.outgoing.filter((o) => o.conn.sourceId === child.id),
 incoming: domain.incoming.filter((i) => i.conn.targetId === child.id),
 }}
 depth={1}
 selectedItemIds={selectedItemIds}
 onSelectItem={onSelectItem}
 onFocusCanvas={onFocusCanvas}
 />
 ))}
 {domain.children.length === 0 && (
 <div className="pl-8 py-1 text-[10px] text-muted-foreground italic">
 하위 노드 없음
 </div>
 )}
 </div>
 )}
 </div>
 );
}

// --- Individual node tree item ---

function NodeTreeItem({
 node,
 depth,
 selectedItemIds,
 onSelectItem,
 onFocusCanvas,
}: {
 node: TreeNode;
 depth: number;
 selectedItemIds: string[];
 onSelectItem: (id: string) => void;
 onFocusCanvas: (id: string) => void;
}) {
 const [expanded, setExpanded] = useState(false);
 const config = NODE_CONFIGS[node.item.type];
 const selected = selectedItemIds.includes(node.item.id);
 const hasRelations = node.outgoing.length > 0 || node.incoming.length > 0;
 const paddingLeft = 12 + depth * 16;

 return (
 <div role="treeitem" aria-expanded={hasRelations ? expanded : undefined}>
 <button
 type="button"
 onClick={() => {
 onSelectItem(node.item.id);
 if (hasRelations) setExpanded((v) => !v);
 }}
 onDoubleClick={() => onFocusCanvas(node.item.id)}
 className={`
 w-full flex items-center gap-2 py-1.5 pr-3 text-left text-xs
 hover:bg-muted transition-colors
 ${selected ? 'bg-blue-900/30 text-primary/80' : 'text-foreground/80'}
 `}
 style={{ paddingLeft }}
 >
 {hasRelations ? (
 <span className="text-foreground0 w-3 text-center">{expanded ? '▼' : '▸'}</span>
 ) : (
 <span className="w-3" />
 )}
 <span
 className="w-2.5 h-2.5 rounded-sm shrink-0"
 style={{ backgroundColor: node.item.color }}
 />
 <span className="truncate">{node.item.label}</span>
 <span className="text-muted-foreground text-[10px] ml-auto shrink-0">
 {config?.label ?? node.item.type}
 </span>
 </button>

 {expanded && hasRelations && (
 <div role="group" style={{ paddingLeft: paddingLeft + 16 }}>
 {node.outgoing.map(({ conn, target }) => {
 const connCfg = CONNECTION_CONFIGS[conn.type];
 return (
 <button
 key={conn.id}
 type="button"
 onClick={() => {
 onSelectItem(target.id);
 onFocusCanvas(target.id);
 }}
 className="w-full flex items-center gap-1.5 py-1 text-left text-[10px] text-foreground0 hover:text-foreground/80"
 >
 <span style={{ color: connCfg.stroke }}>→</span>
 <span className="truncate">{target.label}</span>
 <span className="text-muted-foreground">({connCfg.labelKo})</span>
 </button>
 );
 })}
 {node.incoming.map(({ conn, source }) => {
 const connCfg = CONNECTION_CONFIGS[conn.type];
 return (
 <button
 key={`in-${conn.id}`}
 type="button"
 onClick={() => {
 onSelectItem(source.id);
 onFocusCanvas(source.id);
 }}
 className="w-full flex items-center gap-1.5 py-1 text-left text-[10px] text-foreground0 hover:text-foreground/80"
 >
 <span style={{ color: connCfg.stroke }}>←</span>
 <span className="truncate">{source.label}</span>
 <span className="text-muted-foreground">({connCfg.labelKo})</span>
 </button>
 );
 })}
 </div>
 )}
 </div>
 );
}
