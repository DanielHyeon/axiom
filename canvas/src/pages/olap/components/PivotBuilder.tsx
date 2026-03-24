// src/pages/olap/components/PivotBuilder.tsx

import { usePivotConfig } from '@/features/olap/store/usePivotConfig';
import { DroppableZone } from './DroppableZone';
import { Button } from '@/components/ui/button';
import { ArrowLeftRight, Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface PivotBuilderProps {
 onRunQuery: () => void;
 isQuerying: boolean;
}

export function PivotBuilder({
  const { t } = useTranslation(); onRunQuery, isQuerying }: PivotBuilderProps) {
 const { rows, columns, measures, filters, removeFieldFromZone, setRows, setColumns } = usePivotConfig();

 const handleSwap = () => {
 const tempRows = [...rows];
 setRows(columns);
 setColumns(tempRows);
 };

 const hasRequiredFields = measures.length > 0 && (rows.length > 0 || columns.length > 0);

 return (
 <div className="bg-background flex-1 border-r border-border p-6 flex flex-col">
 <div className="flex justify-between items-center mb-6">
 <h2 className="text-sm font-semibold text-foreground">{t('olapPage.msgf25ab5ff')}</h2>
 <div className="flex gap-2">
 <Button variant="outline" size="sm" onClick={handleSwap} disabled={isQuerying}>
 <ArrowLeftRight size={14} className="mr-1.5" /> {t('olapPage.swapRowCol')}
 </Button>
 <Button
 size="sm"
 onClick={onRunQuery}
 disabled={!hasRequiredFields || isQuerying}
 className="bg-primary hover:bg-primary/90"
 >
 <Play size={14} className="mr-1.5" /> {t('olapPage.runAnalysis')}
 </Button>
 </div>
 </div>

 <div className="bg-card rounded-lg border border-border p-4 space-y-2 relative">
 <DroppableZone id="rows" title={t('olapStudioExt.rowsLabel')} items={rows} onRemove={(id) => removeFieldFromZone('rows', id)} accepts="dimension" />
 <DroppableZone id="columns" title={t('olapStudioExt.colsLabel')} items={columns} onRemove={(id) => removeFieldFromZone('columns', id)} accepts="dimension" />
 <DroppableZone id="measures" title={t('olapPage.msgaf7a72b0')} items={measures} onRemove={(id) => removeFieldFromZone('measures', id)} accepts="measure" />
 <DroppableZone id="filters" title={t('olapStudioExt.filtersLabel')} items={filters.map(f => ({ id: f.dimensionId, name: f.dimensionId, type: 'string' }))} onRemove={(id) => removeFieldFromZone('filters', id)} accepts="dimension" />

 {!hasRequiredFields && (
 <div className="absolute -bottom-8 right-0 text-xs text-warning font-medium">
 {t('olapPage.mddd664b2')}
 </div>
 )}
 </div>
 </div>
 );
}
