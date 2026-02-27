import { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { exportToCsv } from '@/lib/csvExport';
import { ChartRecommender } from './ChartRecommender';
import { SqlPreview } from './SqlPreview';
import { MetadataPanel } from './MetadataPanel';
import { QueryGraphPanel } from './QueryGraphPanel';
import type { ChartConfig, ExecutionMetadata } from '@/features/nl2sql/types/nl2sql';
import {
  BarChart3,
  Table2,
  Code,
  Network,
  Download,
  Sparkles,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

type TabId = 'chart' | 'table' | 'sql' | 'graph';

interface ResultPanelProps {
  sql: string;
  columns: { name: string; type: string }[];
  rows: unknown[][];
  rowCount: number;
  chartConfig: ChartConfig | null;
  summary: string | null;
  metadata: ExecutionMetadata | null;
}

export function ResultPanel({
  sql,
  columns,
  rows,
  rowCount,
  chartConfig,
  summary,
  metadata,
}: ResultPanelProps) {
  const hasChart = !!chartConfig;
  const [activeTab, setActiveTab] = useState<TabId>(hasChart ? 'chart' : 'table');
  const [sorting, setSorting] = useState<SortingState>([]);

  const chartData = useMemo(() => {
    if (!rows.length || !columns.length) return [];
    return rows.map((row) => {
      const obj: Record<string, unknown> = {};
      columns.forEach((col, i) => {
        obj[col.name] = row[i];
      });
      return obj;
    });
  }, [rows, columns]);

  const tableColumns = useMemo<ColumnDef<unknown[], unknown>[]>(
    () =>
      columns.map((col, colIdx) => ({
        id: col.name,
        accessorFn: (row: unknown[]) => row[colIdx],
        header: ({ column }) => (
          <button
            className="flex items-center gap-1 hover:text-black"
            onClick={() => column.toggleSorting()}
          >
            {col.name}
            <ArrowUpDown className="h-3 w-3 text-[#999]" />
          </button>
        ),
        cell: ({ getValue }) => {
          const v = getValue();
          return v == null ? <span className="text-[#999]">--</span> : String(v);
        },
      })),
    [columns]
  );

  const table = useReactTable({
    data: rows,
    columns: tableColumns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 50 } },
  });

  const tabs: { id: TabId; label: string; icon: React.ReactNode; disabled?: boolean }[] = [
    { id: 'chart', label: '차트', icon: <BarChart3 className="h-3.5 w-3.5" />, disabled: !hasChart },
    { id: 'table', label: '테이블', icon: <Table2 className="h-3.5 w-3.5" /> },
    { id: 'sql', label: 'SQL', icon: <Code className="h-3.5 w-3.5" /> },
    { id: 'graph', label: 'Graph', icon: <Network className="h-3.5 w-3.5" /> },
  ];

  const handleExport = () => {
    exportToCsv(columns, rows);
  };

  return (
    <div className="rounded border border-[#E5E5E5] overflow-hidden">
      {/* Tab bar */}
      <div className="flex items-center justify-between border-b border-[#E5E5E5] px-3 py-1.5">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              disabled={tab.disabled}
              onClick={() => !tab.disabled && setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-[Sora] transition-colors',
                activeTab === tab.id
                  ? 'bg-[#F5F5F5] text-black font-medium'
                  : 'text-[#999] hover:text-[#666]',
                tab.disabled && 'opacity-30 cursor-not-allowed'
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 text-xs text-[#5E5E5E] hover:text-black font-[Sora]"
          onClick={handleExport}
        >
          <Download className="h-3.5 w-3.5" />
          CSV
        </Button>
      </div>

      {/* Tab content */}
      <div className="p-3">
        {/* Chart tab */}
        {activeTab === 'chart' && hasChart && (
          <ChartRecommender data={chartData} config={chartConfig!} />
        )}

        {/* Table tab */}
        {activeTab === 'table' && (
          <div>
            <div className="overflow-auto max-h-[500px] rounded border border-[#E5E5E5]">
              <Table>
                <TableHeader>
                  {table.getHeaderGroups().map((hg) => (
                    <TableRow key={hg.id}>
                      {hg.headers.map((header) => (
                        <TableHead key={header.id} className="text-xs whitespace-nowrap font-[IBM_Plex_Mono]">
                          {header.isPlaceholder
                            ? null
                            : flexRender(header.column.columnDef.header, header.getContext())}
                        </TableHead>
                      ))}
                    </TableRow>
                  ))}
                </TableHeader>
                <TableBody>
                  {table.getRowModel().rows.length ? (
                    table.getRowModel().rows.map((row) => (
                      <TableRow key={row.id}>
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id} className="text-xs text-[#5E5E5E] whitespace-nowrap font-[IBM_Plex_Mono]">
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={columns.length} className="h-16 text-center text-[#999]">
                        결과 없음
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            {/* Pagination */}
            {table.getPageCount() > 1 && (
              <div className="flex items-center justify-between pt-2 text-xs text-[#999] font-[IBM_Plex_Mono]">
                <span>
                  {rowCount} rows | Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => table.previousPage()}
                    disabled={!table.getCanPreviousPage()}
                  >
                    <ChevronLeft className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => table.nextPage()}
                    disabled={!table.getCanNextPage()}
                  >
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SQL tab */}
        {activeTab === 'sql' && <SqlPreview sql={sql} />}

        {/* Graph tab */}
        {activeTab === 'graph' && <QueryGraphPanel sql={sql} />}
      </div>

      {/* Summary */}
      {summary && (
        <div className="border-t border-[#E5E5E5] px-3 py-2 flex items-start gap-2">
          <Badge variant="ai" className="shrink-0 mt-0.5">
            <Sparkles className="h-3 w-3 mr-1" />
            AI
          </Badge>
          <p className="text-sm text-[#5E5E5E] font-[IBM_Plex_Mono]">{summary}</p>
        </div>
      )}

      {/* Metadata */}
      <MetadataPanel metadata={metadata} />
    </div>
  );
}
