import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export type CaseStatusFilter = 'ALL' | 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED';

interface CaseFiltersProps {
  status: CaseStatusFilter;
  onStatusChange: (v: CaseStatusFilter) => void;
}

const STATUS_OPTIONS: { value: CaseStatusFilter; label: string }[] = [
  { value: 'ALL', label: '전체 상태' },
  { value: 'PENDING', label: '대기' },
  { value: 'IN_PROGRESS', label: '진행 중' },
  { value: 'COMPLETED', label: '완료' },
  { value: 'REJECTED', label: '반려' },
];

export function CaseFilters({ status, onStatusChange }: CaseFiltersProps) {
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
    </div>
  );
}
