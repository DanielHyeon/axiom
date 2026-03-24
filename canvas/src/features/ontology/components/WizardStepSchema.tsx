/**
 * WizardStepSchema — Step 1: DB 스키마 선택
 * 데이터소스 → 스키마 → 테이블 체크박스 목록
 * KAIR SchemaBasedGenerator.vue / SchemaSelector.vue를 참조하여 이식
 */
import { Database, FolderOpen, Loader2, ChevronLeft, CheckSquare, Square } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { useOntologyWizard } from '../hooks/useOntologyWizard';

type WizardHook = ReturnType<typeof useOntologyWizard>;

interface Props {
  wizard: WizardHook;
}

export function WizardStepSchema({ wizard }: Props) {
  const { t } = useTranslation();
  const {
    datasources,
    datasourcesLoading,
    selectedDatasource,
    setSelectedDatasource,
    schemas,
    schemasLoading,
    selectedSchema,
    setSelectedSchema,
    tables,
    tablesLoading,
    selectedTables,
    toggleTable,
    selectAllTables,
    deselectAllTables,
    goToMapping,
  } = wizard;

  // 단계 1-1: 데이터소스 선택
  if (!selectedDatasource) {
    return (
      <div className="space-y-4">
        <div className="text-center space-y-1">
          <h3 className="text-lg font-semibold text-foreground">{t('ontologyExt.wizard.selectDatasource')}</h3>
          <p className="text-sm text-muted-foreground">{t('ontologyExt.wizard.selectDatasourceHint')}</p>
        </div>

        {datasourcesLoading ? (
          <LoadingState message={t('ontologyExt.wizard.loadingDatasources')} />
        ) : (
          <div className="space-y-2">
            {datasources.map((ds) => (
              <button
                key={ds.name}
                type="button"
                onClick={() => setSelectedDatasource(ds.name)}
                className="w-full flex items-center gap-3 px-4 py-3 bg-card border border-border rounded-lg hover:border-primary hover:bg-primary/5 transition-colors text-left"
              >
                <Database size={18} className="text-primary shrink-0" />
                <span className="flex-1 text-sm font-medium text-foreground">{ds.name}</span>
                <span className="text-xs text-muted-foreground">{ds.type || 'Database'}</span>
              </button>
            ))}
            {datasources.length === 0 && (
              <p className="text-center text-sm text-muted-foreground py-8">
                {t('ontologyExt.wizard.noDatasources')}
              </p>
            )}
          </div>
        )}
      </div>
    );
  }

  // 단계 1-2: 스키마 선택
  if (!selectedSchema) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSelectedDatasource('')}
            className="p-1.5 rounded hover:bg-muted text-muted-foreground"
          >
            <ChevronLeft size={16} />
          </button>
          <h3 className="text-lg font-semibold text-foreground">{t('ontologyExt.wizard.selectSchema')}</h3>
          <span className="px-2 py-0.5 bg-primary text-primary-foreground rounded text-xs font-medium">
            {selectedDatasource}
          </span>
        </div>

        {schemasLoading ? (
          <LoadingState message={t('ontologyExt.wizard.loadingSchemas')} />
        ) : (
          <div className="space-y-2">
            {schemas.map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => setSelectedSchema(s.name)}
                className="w-full flex items-center gap-3 px-4 py-3 bg-card border border-border rounded-lg hover:border-primary hover:bg-primary/5 transition-colors text-left"
              >
                <FolderOpen size={18} className="text-yellow-600 shrink-0" />
                <span className="flex-1 text-sm font-medium text-foreground">{s.name}</span>
                {s.tableCount != null && (
                  <span className="text-xs text-muted-foreground">{t('ontologyExt.wizard.tableCount', { count: s.tableCount })}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 단계 1-3: 테이블 선택
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setSelectedSchema('')}
          className="p-1.5 rounded hover:bg-muted text-muted-foreground"
        >
          <ChevronLeft size={16} />
        </button>
        <h3 className="text-lg font-semibold text-foreground">{t('ontologyExt.wizard.selectTables')}</h3>
        <div className="flex items-center gap-1.5">
          <span className="px-2 py-0.5 bg-primary text-primary-foreground rounded text-xs font-medium">
            {selectedDatasource}
          </span>
          <span className="text-muted-foreground text-xs">/</span>
          <span className="px-2 py-0.5 bg-primary text-primary-foreground rounded text-xs font-medium">
            {selectedSchema}
          </span>
        </div>
      </div>

      {/* 전체 선택 / 해제 */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={selectAllTables}
          className="text-xs text-primary hover:underline"
        >
          {t('whatifExt.dataSelect.selectAll')}
        </button>
        <button
          type="button"
          onClick={deselectAllTables}
          className="text-xs text-muted-foreground hover:underline"
        >
          {t('whatifExt.dataSelect.deselectAll')}
        </button>
        <span className="text-xs text-muted-foreground ml-auto">
          {t('whatifExt.causalEdge.selectedCount', { count: selectedTables.length })}
        </span>
      </div>

      {tablesLoading ? (
        <LoadingState message={t('ontologyExt.wizard.loadingTables')} />
      ) : (
        <div className="space-y-1 max-h-[400px] overflow-y-auto">
          {tables.map((tbl) => {
            const checked = selectedTables.includes(tbl.name);
            return (
              <button
                key={tbl.name}
                type="button"
                onClick={() => toggleTable(tbl.name)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors text-left ${
                  checked ? 'bg-primary/10 border border-primary/30' : 'border border-transparent hover:bg-muted'
                }`}
              >
                {checked ? (
                  <CheckSquare size={16} className="text-primary shrink-0" />
                ) : (
                  <Square size={16} className="text-muted-foreground shrink-0" />
                )}
                <span className={`flex-1 text-sm ${checked ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                  {tbl.name}
                </span>
                {tbl.columnCount != null && (
                  <span className="text-xs text-muted-foreground">{t('ontologyExt.wizard.columnCount', { count: tbl.columnCount })}</span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* 다음 단계 버튼 */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={goToMapping}
          disabled={selectedTables.length === 0}
          className="px-5 py-2.5 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {t('ontologyExt.wizard.layerMapping')} ({t('ontologyExt.wizard.tableCount', { count: selectedTables.length })})
        </button>
      </div>
    </div>
  );
}

function LoadingState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
      <Loader2 size={16} className="animate-spin" />
      <span className="text-sm">{message}</span>
    </div>
  );
}
