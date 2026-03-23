/**
 * CardinalityModal -- FK 관계 생성/편집 모달.
 *
 * 소스/타겟 테이블/컬럼 선택, Cardinality 라디오,
 * 복수 컬럼 매핑(column_pairs), 설명 입력을 제공한다.
 */
import { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Plus, Trash2 } from 'lucide-react';

// --- Props ---

/** 테이블 정보 (컬럼 목록 포함) */
interface TableOption {
  name: string;
  schema: string;
  columns: string[];
}

/** 컬럼 매핑 한 쌍 */
interface PairInput {
  sourceColumn: string;
  targetColumn: string;
}

/** Cardinality 옵션 */
type Cardinality = 'many-to-one' | 'one-to-one' | 'one-to-many' | 'many-to-many';

const CARDINALITY_KEYS: { value: Cardinality; labelKey: string }[] = [
  { value: 'many-to-one', labelKey: 'cardinalityModal.manyToOne' },
  { value: 'one-to-one', labelKey: 'cardinalityModal.oneToOne' },
  { value: 'one-to-many', labelKey: 'cardinalityModal.oneToMany' },
  { value: 'many-to-many', labelKey: 'cardinalityModal.manyToMany' },
];

interface CardinalityModalProps {
  open: boolean;
  onClose: () => void;
  /** 사용 가능한 테이블 목록 (컬럼 정보 포함) */
  tables: TableOption[];
  /** 저장 핸들러 */
  onSave: (payload: {
    source_table: string;
    source_column: string;
    target_table: string;
    target_column: string;
    relationship_type: string;
    description: string;
  }) => void;
  /** 기존 관계 편집 시 전달 */
  initialData?: {
    fromTable?: string;
    toTable?: string;
    fromColumn?: string;
    toColumn?: string;
    cardinality?: Cardinality;
    description?: string;
  };
}

// --- 컴포넌트 ---

export function CardinalityModal({
  open,
  onClose,
  tables,
  onSave,
  initialData,
}: CardinalityModalProps) {
  const { t } = useTranslation();
  // 폼 상태
  const [sourceTable, setSourceTable] = useState('');
  const [targetTable, setTargetTable] = useState('');
  const [pairs, setPairs] = useState<PairInput[]>([{ sourceColumn: '', targetColumn: '' }]);
  const [cardinality, setCardinality] = useState<Cardinality>('many-to-one');
  const [description, setDescription] = useState('');

  // 초기값 설정 (편집 모드)
  useEffect(() => {
    if (open && initialData) {
      setSourceTable(initialData.fromTable || '');
      setTargetTable(initialData.toTable || '');
      setPairs([{
        sourceColumn: initialData.fromColumn || '',
        targetColumn: initialData.toColumn || '',
      }]);
      setCardinality(initialData.cardinality || 'many-to-one');
      setDescription(initialData.description || '');
    } else if (open) {
      // 신규 생성 시 초기화
      setSourceTable('');
      setTargetTable('');
      setPairs([{ sourceColumn: '', targetColumn: '' }]);
      setCardinality('many-to-one');
      setDescription('');
    }
  }, [open, initialData]);

  // 선택된 테이블의 컬럼 목록
  const sourceColumns = tables.find((t) => t.name === sourceTable)?.columns || [];
  const targetColumns = tables.find((t) => t.name === targetTable)?.columns || [];

  // 컬럼 매핑 추가
  const addPair = useCallback(() => {
    setPairs((prev) => [...prev, { sourceColumn: '', targetColumn: '' }]);
  }, []);

  // 컬럼 매핑 삭제
  const removePair = useCallback((idx: number) => {
    setPairs((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // 컬럼 매핑 변경
  const updatePair = useCallback((idx: number, field: keyof PairInput, value: string) => {
    setPairs((prev) => prev.map((p, i) => (i === idx ? { ...p, [field]: value } : p)));
  }, []);

  // 저장 가능 여부
  const canSave = sourceTable && targetTable && pairs.some((p) => p.sourceColumn && p.targetColumn);

  // 저장 핸들러
  const handleSave = useCallback(() => {
    const validPairs = pairs.filter((p) => p.sourceColumn && p.targetColumn);
    if (!validPairs.length) return;

    // 첫 번째 매핑을 메인으로 저장 (API가 단일 컬럼 쌍만 지원하는 경우)
    const first = validPairs[0];
    onSave({
      source_table: sourceTable,
      source_column: first.sourceColumn,
      target_table: targetTable,
      target_column: first.targetColumn,
      relationship_type: cardinality,
      description,
    });

    // 추가 매핑이 있으면 각각 저장
    for (let i = 1; i < validPairs.length; i++) {
      onSave({
        source_table: sourceTable,
        source_column: validPairs[i].sourceColumn,
        target_table: targetTable,
        target_column: validPairs[i].targetColumn,
        relationship_type: cardinality,
        description,
      });
    }

    onClose();
  }, [sourceTable, targetTable, pairs, cardinality, description, onSave, onClose]);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="font-heading text-[15px]">
            {initialData ? t('cardinalityModal.editTitle') : t('cardinalityModal.addTitle')}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* 소스/타겟 테이블 선택 */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-[11px] font-mono text-foreground/50">{t('cardinalityModal.sourceTable')}</Label>
              <select
                value={sourceTable}
                onChange={(e) => setSourceTable(e.target.value)}
                className="w-full rounded border border-border bg-card px-2 py-1.5 text-[12px] font-mono"
              >
                <option value="">{t('cardinalityModal.selectPlaceholder')}</option>
                {tables.map((tbl) => (
                  <option key={tbl.name} value={tbl.name}>{tbl.schema}.{tbl.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-[11px] font-mono text-foreground/50">{t('cardinalityModal.targetTable')}</Label>
              <select
                value={targetTable}
                onChange={(e) => setTargetTable(e.target.value)}
                className="w-full rounded border border-border bg-card px-2 py-1.5 text-[12px] font-mono"
              >
                <option value="">{t('cardinalityModal.selectPlaceholder')}</option>
                {tables.map((tbl) => (
                  <option key={tbl.name} value={tbl.name}>{tbl.schema}.{tbl.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* 컬럼 매핑 */}
          <div className="space-y-2">
            <Label className="text-[11px] font-mono text-foreground/50">{t('cardinalityModal.columnMapping')}</Label>
            {pairs.map((pair, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <select
                  value={pair.sourceColumn}
                  onChange={(e) => updatePair(idx, 'sourceColumn', e.target.value)}
                  className="flex-1 rounded border border-border bg-card px-2 py-1 text-[11px] font-mono"
                  disabled={!sourceTable}
                >
                  <option value="">{t('cardinalityModal.sourceColumn')}</option>
                  {sourceColumns.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <span className="text-foreground/30 text-[10px]">→</span>
                <select
                  value={pair.targetColumn}
                  onChange={(e) => updatePair(idx, 'targetColumn', e.target.value)}
                  className="flex-1 rounded border border-border bg-card px-2 py-1 text-[11px] font-mono"
                  disabled={!targetTable}
                >
                  <option value="">{t('cardinalityModal.targetColumn')}</option>
                  {targetColumns.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                {pairs.length > 1 && (
                  <button type="button" onClick={() => removePair(idx)} className="text-red-400 hover:text-red-600">
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={addPair}
              className="flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-600 font-mono"
            >
              <Plus className="h-3 w-3" /> {t('cardinalityModal.addMapping')}
            </button>
          </div>

          {/* Cardinality 관계 유형 선택 */}
          <div className="space-y-1.5">
            <Label className="text-[11px] font-mono text-foreground/50">{t('cardinalityModal.relationType')}</Label>
            <div className="flex flex-wrap gap-2">
              {CARDINALITY_KEYS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setCardinality(opt.value)}
                  className={`px-2 py-1 rounded text-[10px] font-mono border transition-colors ${
                    cardinality === opt.value
                      ? 'border-blue-400 bg-blue-50 text-blue-700'
                      : 'border-border text-foreground/40 hover:border-border'
                  }`}
                >
                  {t(opt.labelKey)}
                </button>
              ))}
            </div>
          </div>

          {/* 설명 입력 (선택 사항) */}
          <div className="space-y-1.5">
            <Label className="text-[11px] font-mono text-foreground/50">{t('cardinalityModal.descriptionOptional')}</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('cardinalityModal.descriptionPlaceholder')}
              className="text-[11px] font-mono"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!canSave}>
            {initialData ? t('common.edit') : t('common.add')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
