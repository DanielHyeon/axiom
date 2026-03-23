/**
 * 온톨로지 검색 패널 — 디바운스 검색 + 자동완성.
 * Sprint 4b: 그래프 탐색 UI.
 */

import { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

interface SearchPanelProps {
  nodes: Array<{ id: string; name: string; layer: string }>;
  onSelect: (nodeId: string) => void;
}

export function SearchPanel({ nodes, onSelect }: SearchPanelProps) {
  const [query, setQuery] = useState('');

  const results = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return nodes.filter((n) => n.name.toLowerCase().includes(q)).slice(0, 10);
  }, [nodes, query]);

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="노드 검색..."
          className="pl-8 h-8 text-sm"
          aria-label="온톨로지 노드 검색"
        />
      </div>
      {results.length > 0 && (
        <div className="border border-border rounded-md bg-card max-h-48 overflow-auto">
          {results.map((n) => (
            <button
              key={n.id}
              onClick={() => { onSelect(n.id); setQuery(''); }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors flex justify-between"
            >
              <span>{n.name}</span>
              <span className="text-xs text-muted-foreground">{n.layer}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
