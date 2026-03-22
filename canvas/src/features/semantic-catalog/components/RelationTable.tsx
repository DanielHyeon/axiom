/**
 * 온톨로지 관계 테이블 — PG 기반 관계 CRUD (주체 → 술어 → 객체)
 *
 * 관계의 가중치, 신뢰도, 유효 기간을 시각적으로 표시하며
 * 인라인 폼으로 새 관계를 등록하고 행별 삭제를 지원한다.
 */
import { useState } from 'react';
import { GitFork, Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import type { OntologyRelation, PredicateType } from '../types/semantic';

// ── 술어 타입별 배지 색상 ──
const PREDICATE_COLORS: Record<PredicateType, string> = {
  is_a: 'bg-violet-50 text-violet-700',
  part_of: 'bg-blue-50 text-blue-700',
  relates_to: 'bg-slate-100 text-slate-700',
  derives_from: 'bg-emerald-50 text-emerald-700',
  equivalent_to: 'bg-amber-50 text-amber-700',
  owned_by: 'bg-rose-50 text-rose-700',
  constrained_by: 'bg-cyan-50 text-cyan-700',
};

const PREDICATE_OPTIONS: PredicateType[] = [
  'is_a', 'part_of', 'relates_to', 'derives_from', 'equivalent_to', 'owned_by', 'constrained_by',
];

interface Props {
  relations: OntologyRelation[];
  onCreate?: (data: Partial<OntologyRelation>) => void;
  onDelete?: (relationId: string) => void;
  isCreating?: boolean;
  isDeleting?: boolean;
}

/** 새 관계 등록 인라인 폼의 초기값 */
const EMPTY_FORM = {
  subject_concept_id: '',
  predicate_type: 'relates_to' as PredicateType,
  object_concept_id: '',
  cardinality: '1:N',
  directionality: 'unidirectional',
  weight: 1.0,
  confidence: 1.0,
  effective_from: '',
  effective_to: '',
};

export function RelationTable({ relations, onCreate, onDelete, isCreating, isDeleting }: Props) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  /** 폼 필드 변경 핸들러 */
  const handleChange = (field: string, value: string | number) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  /** 관계 등록 제출 */
  const handleSubmit = () => {
    if (!form.subject_concept_id || !form.object_concept_id) return;
    onCreate?.({
      ...form,
      weight: Number(form.weight),
      confidence: Number(form.confidence),
      effective_from: form.effective_from || undefined,
      effective_to: form.effective_to || undefined,
    });
    setForm({ ...EMPTY_FORM });
    setShowForm(false);
  };

  return (
    <div className="rounded-lg border">
      {/* 헤더 + 등록 버튼 */}
      <div className="flex items-center justify-between border-b bg-muted/50 px-3 py-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <GitFork className="h-4 w-4 text-violet-600" />
          온톨로지 관계
        </div>
        {onCreate && (
          <button
            className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
            onClick={() => setShowForm(!showForm)}
          >
            {showForm ? <ChevronUp className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
            {showForm ? '닫기' : '관계 등록'}
          </button>
        )}
      </div>

      {/* 인라인 등록 폼 (접힘/펼침) */}
      {showForm && (
        <div className="border-b bg-muted/20 px-4 py-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            {/* 주체 개념 */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">주체 개념 ID</label>
              <input
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                placeholder="concept_..."
                value={form.subject_concept_id}
                onChange={(e) => handleChange('subject_concept_id', e.target.value)}
              />
            </div>
            {/* 술어 타입 */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">술어 타입</label>
              <select
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                value={form.predicate_type}
                onChange={(e) => handleChange('predicate_type', e.target.value)}
              >
                {PREDICATE_OPTIONS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            {/* 객체 개념 */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">객체 개념 ID</label>
              <input
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                placeholder="concept_..."
                value={form.object_concept_id}
                onChange={(e) => handleChange('object_concept_id', e.target.value)}
              />
            </div>
            {/* 카디널리티 */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">카디널리티</label>
              <select
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                value={form.cardinality}
                onChange={(e) => handleChange('cardinality', e.target.value)}
              >
                <option value="1:1">1:1</option>
                <option value="1:N">1:N</option>
                <option value="N:1">N:1</option>
                <option value="N:M">N:M</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            {/* 가중치 */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">가중치 (0~1)</label>
              <input
                type="number"
                min={0}
                max={1}
                step={0.1}
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                value={form.weight}
                onChange={(e) => handleChange('weight', parseFloat(e.target.value) || 0)}
              />
            </div>
            {/* 신뢰도 */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">신뢰도 (0~1)</label>
              <input
                type="number"
                min={0}
                max={1}
                step={0.1}
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                value={form.confidence}
                onChange={(e) => handleChange('confidence', parseFloat(e.target.value) || 0)}
              />
            </div>
            {/* 유효 시작 */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">유효 시작일</label>
              <input
                type="date"
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                value={form.effective_from}
                onChange={(e) => handleChange('effective_from', e.target.value)}
              />
            </div>
            {/* 유효 종료 */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">유효 종료일</label>
              <input
                type="date"
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                value={form.effective_to}
                onChange={(e) => handleChange('effective_to', e.target.value)}
              />
            </div>
          </div>
          <button
            className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            disabled={isCreating || !form.subject_concept_id || !form.object_concept_id}
            onClick={handleSubmit}
          >
            {isCreating ? '등록 중...' : '등록'}
          </button>
        </div>
      )}

      {/* 테이블 */}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium">관계 ID</th>
            <th className="px-3 py-2 text-left font-medium">주체 → 술어 → 객체</th>
            <th className="px-3 py-2 text-center font-medium">카디널리티</th>
            <th className="px-3 py-2 text-center font-medium">가중치</th>
            <th className="px-3 py-2 text-center font-medium">신뢰도</th>
            <th className="px-3 py-2 text-left font-medium">유효 기간</th>
            {onDelete && <th className="px-3 py-2 w-10" />}
          </tr>
        </thead>
        <tbody>
          {relations.map((r) => {
            const badgeClass = PREDICATE_COLORS[r.predicate_type as PredicateType] ?? PREDICATE_COLORS.relates_to;
            return (
              <tr key={r.relation_id} className="border-b hover:bg-muted/30">
                <td className="px-3 py-2 font-mono text-xs">{r.relation_id}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-mono text-xs">{r.subject_concept_id}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${badgeClass}`}>
                      {r.predicate_type}
                    </span>
                    <span className="text-muted-foreground">→</span>
                    <span className="font-mono text-xs">{r.object_concept_id}</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-center">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                    {r.cardinality}
                  </span>
                </td>
                <td className="px-3 py-2 text-center tabular-nums text-xs">
                  {r.weight.toFixed(2)}
                </td>
                <td className="px-3 py-2 text-center tabular-nums text-xs">
                  <span className={r.confidence < 0.5 ? 'text-red-600 font-medium' : 'text-muted-foreground'}>
                    {r.confidence.toFixed(2)}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {r.effective_from || r.effective_to ? (
                    <span>{r.effective_from || '...'} ~ {r.effective_to || '...'}</span>
                  ) : (
                    <span>무기한</span>
                  )}
                </td>
                {onDelete && (
                  <td className="px-3 py-2">
                    <button
                      className="p-1 rounded hover:bg-red-50 text-red-500 hover:text-red-700"
                      title="삭제"
                      disabled={isDeleting}
                      onClick={() => onDelete(r.relation_id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      {relations.length === 0 && (
        <div className="py-8 text-center text-muted-foreground text-sm">등록된 관계가 없습니다</div>
      )}
    </div>
  );
}
