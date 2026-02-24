function escapeCsvField(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

export function exportToCsv(
  columns: { name: string }[],
  rows: unknown[][],
  filename?: string
): void {
  const header = columns.map((c) => escapeCsvField(c.name)).join(',');
  const body = rows
    .map((row) =>
      row.map((cell) => escapeCsvField(cell == null ? '' : String(cell))).join(',')
    )
    .join('\n');
  const csv = header + '\n' + body;
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || `nl2sql-result-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
