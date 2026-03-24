import { useTranslation } from 'react-i18next';
import {
 Select,
 SelectContent,
 SelectItem,
 SelectTrigger,
 SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

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

const STATUS_OPTIONS: { value: CaseStatusFilter; label: string }[] = [
 { value: 'ALL', label: t('dataQualityExt.allStatus') },
 { value: 'PENDING', label: t('ontologyWizardExt.statusBadge.pending') },
 { value: 'IN_PROGRESS', label: t('ontologyWizardExt.statusBadge.in_progress') },
 { value: 'COMPLETED', label: t('ontologyWizardExt.statusBadge.complete') },
 { value: 'REJECTED', label: t('caseDashboardExt.status.REJECTED') },
];

const TYPE_OPTIONS: { value: CaseTypeFilter; label: string }[] = [
 { value: 'ALL', label: t('caseDashboardExt.priority.ALL') },
 { value: 'CRITICAL', label: t('caseDashboardExt.priority.CRITICAL') },
 { value: 'HIGH', label: t('caseDashboardExt.priority.HIGH') },
 { value: 'MEDIUM', label: t('caseDashboardExt.priority.MEDIUM') },
 { value: 'LOW', label: t('caseDashboardExt.priority.LOW') },
];

export function CaseFilters({
 status,
 onStatusChange,
 type = 'ALL',
 onTypeChange,
 searchQuery = '',
 onSearchQueryChange,
}: CaseFiltersProps) {
 return (
 <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-2 sm:gap-4">
 <Select value={status} onValueChange={(v) => onStatusChange(v as CaseStatusFilter)}>
 <SelectTrigger className="w-full sm:w-[180px]">
 <SelectValue placeholder={t('dataQualityExt.incidentCols.status')} />
 </SelectTrigger>
 <SelectContent>
 {STATUS_OPTIONS.map((opt) => (
 <SelectItem key={opt.value} value={opt.value}>
 {opt.label}
 </SelectItem>
 ))}
 </SelectContent>
 </Select>
 {onTypeChange && (
 <Select value={type} onValueChange={(v) => onTypeChange(v as CaseTypeFilter)}>
 <SelectTrigger className="w-full sm:w-[180px]">
 <SelectValue placeholder={t('caseDashboardExt.caseTable.priority')} />
 </SelectTrigger>
 <SelectContent>
 {TYPE_OPTIONS.map((opt) => (
 <SelectItem key={opt.value} value={opt.value}>
 {opt.label}
 </SelectItem>
 ))}
 </SelectContent>
 </Select>
 )}
 {onSearchQueryChange && (
 <div className="relative w-full sm:w-56">
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
