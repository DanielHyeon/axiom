import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDatasources } from '@/features/nl2sql/api/oracleNl2sqlApi';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Database } from 'lucide-react';

interface DatasourceSelectorProps {
  value: string;
  onChange: (datasourceId: string) => void;
}

export function DatasourceSelector({ value, onChange }: DatasourceSelectorProps) {
  const { data: datasources = [], isLoading } = useQuery({
    queryKey: ['nl2sql', 'datasources'],
    queryFn: getDatasources,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (!value && datasources.length > 0) {
      onChange(datasources[0].id);
    }
  }, [datasources, value, onChange]);

  if (isLoading) {
    return (
      <div className="h-10 w-56 animate-pulse rounded-md bg-neutral-800" />
    );
  }

  if (datasources.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-neutral-500">
        <Database className="h-4 w-4" />
        <span>데이터소스 없음</span>
      </div>
    );
  }

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-56 border-neutral-700 bg-neutral-900">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-neutral-400" />
          <SelectValue placeholder="데이터소스 선택" />
        </div>
      </SelectTrigger>
      <SelectContent>
        {datasources.map((ds) => (
          <SelectItem key={ds.id} value={ds.id}>
            {ds.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
