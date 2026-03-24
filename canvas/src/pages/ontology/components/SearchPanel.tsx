import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

export function SearchPanel() {
  const { t } = useTranslation();
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
 <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-foreground/60" />
 <Input
 type="text"
 placeholder={t('ontologyExt.nodeDetail.searchPlaceholder')}
 className="pl-9 bg-card border-border text-foreground placeholder:text-foreground/60 font-mono text-[13px]"
 value={localQuery}
 onChange={(e) => setLocalQuery(e.target.value)}
 />
 </div>
 );
}
