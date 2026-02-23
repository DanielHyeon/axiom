import { useState, useEffect, useCallback } from 'react';
import { getDatasourceSchemas, getDatasourceTables } from '../api/weaverDatasourceApi';
import { ChevronRight, ChevronDown, Database, FolderOpen, Table } from 'lucide-react';

interface SchemaExplorerProps {
  selectedDsName: string | null;
  onSelectDs: (name: string) => void;
  datasourceNames: string[];
}

export function SchemaExplorer({ selectedDsName, onSelectDs, datasourceNames }: SchemaExplorerProps) {
  const [schemas, setSchemas] = useState<string[]>([]);
  const [schemasLoading, setSchemasLoading] = useState(false);
  const [expandedSchema, setExpandedSchema] = useState<string | null>(null);
  const [tablesMap, setTablesMap] = useState<Record<string, string[]>>({});
  const [tablesLoading, setTablesLoading] = useState<string | null>(null);

  const loadSchemas = useCallback(async (name: string) => {
    setSchemasLoading(true);
    setSchemas([]);
    setExpandedSchema(null);
    setTablesMap({});
    try {
      const res = await getDatasourceSchemas(name);
      setSchemas(res.schemas ?? []);
    } catch {
      setSchemas([]);
    } finally {
      setSchemasLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedDsName) loadSchemas(selectedDsName);
    else {
      setSchemas([]);
      setExpandedSchema(null);
      setTablesMap({});
    }
  }, [selectedDsName, loadSchemas]);

  const loadTables = useCallback(async (dsName: string, schema: string) => {
    if (tablesMap[schema]) return;
    setTablesLoading(schema);
    try {
      const res = await getDatasourceTables(dsName, schema);
      setTablesMap((prev) => ({ ...prev, [schema]: res.tables ?? [] }));
    } catch {
      setTablesMap((prev) => ({ ...prev, [schema]: [] }));
    } finally {
      setTablesLoading(null);
    }
  }, [tablesMap]);

  const toggleSchema = (schema: string) => {
    if (expandedSchema === schema) {
      setExpandedSchema(null);
      return;
    }
    setExpandedSchema(schema);
    if (selectedDsName && !tablesMap[schema]) loadTables(selectedDsName, schema);
  };

  return (
    <div className="border border-neutral-200 rounded-lg bg-white overflow-hidden">
      <div className="p-3 border-b border-neutral-200 bg-neutral-50 font-medium text-sm">메타데이터 트리</div>
      <div className="p-2 max-h-80 overflow-y-auto">
        {datasourceNames.length === 0 && (
          <p className="text-neutral-500 text-xs p-2">데이터소스를 먼저 추가하세요.</p>
        )}
        {datasourceNames.map((name) => (
          <div key={name}>
            <button
              type="button"
              onClick={() => onSelectDs(selectedDsName === name ? '' : name)}
              className={`flex items-center gap-2 w-full text-left px-2 py-1.5 rounded text-sm ${selectedDsName === name ? 'bg-blue-50 text-blue-700' : 'hover:bg-neutral-100 text-neutral-700'}`}
            >
              {selectedDsName === name ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <Database size={14} />
              {name}
            </button>
            {selectedDsName === name && (
              <div className="ml-4 mt-0.5">
                {schemasLoading && <p className="text-xs text-neutral-500 p-1">로딩 중...</p>}
                {!schemasLoading && schemas.length === 0 && (
                  <p className="text-xs text-neutral-500 p-1">스키마 없음</p>
                )}
                {!schemasLoading &&
                  schemas.map((schema) => (
                    <div key={schema}>
                      <button
                        type="button"
                        onClick={() => toggleSchema(schema)}
                        className={`flex items-center gap-2 w-full text-left px-2 py-1 rounded text-xs ${expandedSchema === schema ? 'bg-neutral-100' : 'hover:bg-neutral-50'}`}
                      >
                        {expandedSchema === schema ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        <FolderOpen size={12} className="text-amber-600" />
                        {schema}
                      </button>
                      {expandedSchema === schema && (
                        <div className="ml-4 py-1">
                          {tablesLoading === schema && <p className="text-xs text-neutral-400 px-2">로딩 중...</p>}
                          {tablesMap[schema]?.map((table) => (
                            <div key={table} className="flex items-center gap-2 px-2 py-0.5 text-xs text-neutral-600">
                              <Table size={12} />
                              {table}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
