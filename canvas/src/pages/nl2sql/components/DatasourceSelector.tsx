import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDatasources } from '@/features/nl2sql/api/oracleNl2sqlApi';
import { useTranslation } from 'react-i18next';
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

export function DatasourceSelector({
  value, onChange }: DatasourceSelectorProps) {
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
 <div className="h-10 w-56 animate-pulse rounded-md bg-border" />
 );
 }

 if (datasources.length === 0) {
 return (
 <div className="flex items-center gap-2 text-sm text-foreground/60 font-mono">
 <Database className="h-4 w-4" />
 <span>{t('nl2sqlPage.msgea674af3')}</span>
 </div>
 );
 }

 return (
 <Select value={value} onValueChange={onChange}>
 <SelectTrigger className="w-56 border-border bg-card">
 <div className="flex items-center gap-2">
 <Database className="h-4 w-4 text-foreground/60" />
 <SelectValue placeholder={t('ontologyExt.generator.selectDatasource')} />
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
