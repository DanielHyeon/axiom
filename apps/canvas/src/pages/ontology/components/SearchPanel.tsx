import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import { useState, useEffect } from 'react';

export function SearchPanel() {
    const { filters, setSearchQuery } = useOntologyStore();
    const [localQuery, setLocalQuery] = useState(filters.query);

    // Debounce search
    useEffect(() => {
        const timer = setTimeout(() => {
            setSearchQuery(localQuery);
        }, 300);
        return () => clearTimeout(timer);
    }, [localQuery, setSearchQuery]);

    return (
        <div className="relative w-full max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-neutral-500" />
            <Input
                type="text"
                placeholder="노드 검색..."
                className="pl-9 bg-[#1a1a1a] border-neutral-800 text-neutral-200"
                value={localQuery}
                onChange={(e) => setLocalQuery(e.target.value)}
            />
        </div>
    );
}
