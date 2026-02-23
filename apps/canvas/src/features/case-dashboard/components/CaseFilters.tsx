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
  { value: 'ALL', label: '전체 상태' },
  { value: 'PENDING', label: '대기' },
  { value: 'IN_PROGRESS', label: '진행 중' },
  { value: 'COMPLETED', label: '완료' },
  { value: 'REJECTED', label: '반려' },
];

const TYPE_OPTIONS: { value: CaseTypeFilter; label: string }[] = [
  { value: 'ALL', label: '전체 우선순위' },
  { value: 'CRITICAL', label: '긴급' },
  { value: 'HIGH', label: '높음' },
  { value: 'MEDIUM', label: '중간' },
  { value: 'LOW', label: '낮음' },
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
    <div className="flex flex-wrap items-center gap-4">
      <Select value={status} onValueChange={(v) => onStatusChange(v as CaseStatusFilter)}>
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="상태" />
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
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="우선순위" />
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
        <div className="relative w-56">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-secondary-foreground" aria-hidden />
          <Input
            type="search"
            placeholder="케이스명 검색..."
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            className="pl-8 bg-background"
            aria-label="케이스명 검색"
          />
        </div>
      )}
    </div>
  );
}
