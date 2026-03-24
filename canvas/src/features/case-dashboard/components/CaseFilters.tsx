import {
 Select,
 SelectContent,
 SelectItem,
 SelectTrigger,
 SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export type CaseStatusFilter = 'ALL' | 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED';
export type CaseTypeFilter = 'ALL' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

interface CaseFiltersProps {
 status: CaseStatusFilter;
 onStatusChange: (v: CaseStatusFilter) => void;
 type?: CaseTypeFilter;
 onTypeChange?: (v: CaseTypeFilter) => void;
 searchQuery?: string;
 onSearchQueryChange?: (v: string) => void;
}

const STATUS_OPTIONS: { value: CaseStatusFilter; labelKey: string }[] = [
 { value: 'ALL', labelKey: 'caseDashboardExt.status.ALL' },
 { value: 'PENDING', labelKey: 'caseDashboardExt.status.PENDING' },
 { value: 'IN_PROGRESS', labelKey: 'caseDashboardExt.status.IN_PROGRESS' },
 { value: 'COMPLETED', labelKey: 'caseDashboardExt.status.COMPLETED' },
 { value: 'REJECTED', labelKey: 'caseDashboardExt.status.REJECTED' },
];

const TYPE_OPTIONS: { value: CaseTypeFilter; labelKey: string }[] = [
 { value: 'ALL', labelKey: 'caseDashboardExt.priority.ALL' },
 { value: 'CRITICAL', labelKey: 'caseDashboardExt.priority.CRITICAL' },
 { value: 'HIGH', labelKey: 'caseDashboardExt.priority.HIGH' },
 { value: 'MEDIUM', labelKey: 'caseDashboardExt.priority.MEDIUM' },
 { value: 'LOW', labelKey: 'caseDashboardExt.priority.LOW' },
];

export function CaseFilters({
 status,
 onStatusChange,
 type = 'ALL',
 onTypeChange,
 searchQuery = '',
 onSearchQueryChange,
}: CaseFiltersProps) {
 const { t } = useTranslation();
 return (
 <div className="flex flex-wrap items-center gap-4">
 <Select value={status} onValueChange={(v) => onStatusChange(v as CaseStatusFilter)}>
 <SelectTrigger className="w-[180px]">
 <SelectValue placeholder={t('caseDashboardExt.statusPlaceholder')} />
 </SelectTrigger>
 <SelectContent>
 {STATUS_OPTIONS.map((opt) => (
 <SelectItem key={opt.value} value={opt.value}>
 {t(opt.labelKey)}
 </SelectItem>
 ))}
 </SelectContent>
 </Select>
 {onTypeChange && (
 <Select value={type} onValueChange={(v) => onTypeChange(v as CaseTypeFilter)}>
 <SelectTrigger className="w-[180px]">
 <SelectValue placeholder={t('caseDashboardExt.priorityPlaceholder')} />
 </SelectTrigger>
 <SelectContent>
 {TYPE_OPTIONS.map((opt) => (
 <SelectItem key={opt.value} value={opt.value}>
 {t(opt.labelKey)}
 </SelectItem>
 ))}
 </SelectContent>
 </Select>
 )}
 {onSearchQueryChange && (
 <div className="relative w-56">
 <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-secondary-foreground" aria-hidden />
 <Input
 type="search"
 placeholder={t('caseDashboardExt.searchCase')}
 value={searchQuery}
 onChange={(e) => onSearchQueryChange(e.target.value)}
 className="pl-8 bg-background"
 aria-label={t('caseDashboardExt.searchCaseAria')}
 />
 </div>
 )}
 </div>
 );
}
