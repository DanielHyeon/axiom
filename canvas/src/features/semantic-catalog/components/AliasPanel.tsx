/**
 * 별칭 패널 — 별칭 그룹 + 확장 규칙 2단 테이블
 *
 * 별칭 그룹 목록을 상단에, 선택한 그룹의 확장 규칙을 하단에 표시한다.
 * 그룹 생성 폼과 규칙 활성화/비활성화 토글을 지원한다.
 */
import { useState } from 'react';
import { Tags, Plus, ChevronUp } from 'lucide-react';
import type { AliasGroup, ExpansionRule, ExpansionRuleType, ExpansionRuleStatus } from '../types/semantic';

// ── 규칙 타입 배지 색상 ──
const RULE_TYPE_COLORS: Record<ExpansionRuleType, string> = {
  EXACT: 'bg-blue-50 text-blue-700',
  NORMALIZED_EXACT: 'bg-cyan-50 text-cyan-700',
  TOKEN_SET: 'bg-emerald-50 text-emerald-700',
  REGEX: 'bg-violet-50 text-violet-700',
  TIME_ALIAS: 'bg-amber-50 text-amber-700',
  ACRONYM: 'bg-rose-50 text-rose-700',
  NEGATIVE_RULE: 'bg-red-100 text-red-800',
};

// ── 상태 배지 색상 ──
const STATUS_COLORS: Record<ExpansionRuleStatus, string> = {
  ACTIVE: 'bg-green-100 text-green-800',
  DEPRECATED: 'bg-red-100 text-red-800',
};

interface Props {
  aliasGroups: AliasGroup[];
  expansionRules: ExpansionRule[];
  selectedGroupId?: string;
  onSelectGroup?: (groupId: string) => void;
  onCreateGroup?: (data: Partial<AliasGroup>) => void;
  onActivateRule?: (ruleId: string) => void;
  onDeprecateRule?: (ruleId: string) => void;
  isCreatingGroup?: boolean;
}

const EMPTY_GROUP = {
  domain_id: '',
  canonical_term_id: '',
  group_name: '',
  language_code: 'ko',
};

export function AliasPanel({
  aliasGroups,
  expansionRules,
  selectedGroupId,
  onSelectGroup,
  onCreateGroup,
  onActivateRule,
  onDeprecateRule,
  isCreatingGroup,
}: Props) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_GROUP });

  const handleChange = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = () => {
    if (!form.group_name || !form.domain_id) return;
    onCreateGroup?.(form);
    setForm({ ...EMPTY_GROUP });
    setShowForm(false);
  };

  return (
    <div className="space-y-4">
      {/* ═══════ 별칭 그룹 섹션 ═══════ */}
      <div className="rounded-lg border">
        <div className="flex items-center justify-between border-b bg-muted/50 px-3 py-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Tags className="h-4 w-4 text-teal-600" />
            별칭 그룹
          </div>
          {onCreateGroup && (
            <button
              className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
              onClick={() => setShowForm(!showForm)}
            >
              {showForm ? <ChevronUp className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
              {showForm ? '닫기' : '그룹 등록'}
            </button>
          )}
        </div>

        {/* 그룹 생성 폼 */}
        {showForm && (
          <div className="border-b bg-muted/20 px-4 py-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">그룹 이름</label>
                <input
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  value={form.group_name}
                  onChange={(e) => handleChange('group_name', e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">도메인 ID</label>
                <input
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  value={form.domain_id}
                  onChange={(e) => handleChange('domain_id', e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">표준 용어 ID</label>
                <input
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  value={form.canonical_term_id}
                  onChange={(e) => handleChange('canonical_term_id', e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">언어</label>
                <select
                  className="w-full rounded-md border px-2 py-1.5 text-sm"
                  value={form.language_code}
                  onChange={(e) => handleChange('language_code', e.target.value)}
                >
                  <option value="ko">한국어</option>
                  <option value="en">영어</option>
                </select>
              </div>
            </div>
            <button
              className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              disabled={isCreatingGroup || !form.group_name || !form.domain_id}
              onClick={handleSubmit}
            >
              {isCreatingGroup ? '등록 중...' : '등록'}
            </button>
          </div>
        )}

        {/* 그룹 테이블 */}
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2 text-left font-medium">그룹 이름</th>
              <th className="px-3 py-2 text-left font-medium">도메인</th>
              <th className="px-3 py-2 text-left font-medium">표준 용어 ID</th>
              <th className="px-3 py-2 text-center font-medium">언어</th>
              <th className="px-3 py-2 text-center font-medium">상태</th>
            </tr>
          </thead>
          <tbody>
            {aliasGroups.map((g) => (
              <tr
                key={g.id}
                className={`border-b cursor-pointer hover:bg-muted/30 ${selectedGroupId === g.id ? 'bg-primary/5 ring-1 ring-inset ring-primary/20' : ''}`}
                onClick={() => onSelectGroup?.(g.id)}
              >
                <td className="px-3 py-2 font-medium">{g.group_name}</td>
                <td className="px-3 py-2 text-muted-foreground text-xs">{g.domain_id}</td>
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{g.canonical_term_id}</td>
                <td className="px-3 py-2 text-center text-xs">{g.language_code}</td>
                <td className="px-3 py-2 text-center">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${g.status === 'ACTIVE' ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-600'}`}>
                    {g.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {aliasGroups.length === 0 && (
          <div className="py-6 text-center text-muted-foreground text-sm">등록된 별칭 그룹이 없습니다</div>
        )}
      </div>

      {/* ═══════ 확장 규칙 섹션 (선택된 그룹이 있을 때만) ═══════ */}
      {selectedGroupId && (
        <div className="rounded-lg border">
          <div className="border-b bg-muted/50 px-3 py-2">
            <span className="text-sm font-medium">확장 규칙</span>
            <span className="ml-2 text-xs text-muted-foreground">
              그룹: {aliasGroups.find((g) => g.id === selectedGroupId)?.group_name ?? selectedGroupId}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left font-medium">타입</th>
                <th className="px-3 py-2 text-left font-medium">매칭 패턴</th>
                <th className="px-3 py-2 text-center font-medium">부스트</th>
                <th className="px-3 py-2 text-center font-medium">우선순위</th>
                <th className="px-3 py-2 text-center font-medium">상태</th>
                {(onActivateRule || onDeprecateRule) && <th className="px-3 py-2 w-20" />}
              </tr>
            </thead>
            <tbody>
              {expansionRules.map((r) => {
                const typeBadge = RULE_TYPE_COLORS[r.rule_type] ?? 'bg-slate-100 text-slate-700';
                const statusBadge = STATUS_COLORS[r.status] ?? STATUS_COLORS.ACTIVE;
                return (
                  <tr key={r.id} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-2">
                      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${typeBadge}`}>
                        {r.rule_type}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs max-w-[300px] truncate" title={r.match_pattern}>
                      {r.match_pattern}
                    </td>
                    <td className="px-3 py-2 text-center tabular-nums text-xs">{r.boost.toFixed(1)}</td>
                    <td className="px-3 py-2 text-center tabular-nums text-xs">{r.priority}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge}`}>
                        {r.status}
                      </span>
                    </td>
                    {(onActivateRule || onDeprecateRule) && (
                      <td className="px-3 py-2 text-center">
                        {r.status === 'DEPRECATED' && onActivateRule && (
                          <button
                            className="text-xs px-2 py-0.5 rounded bg-green-50 hover:bg-green-100 text-green-700"
                            onClick={() => onActivateRule(r.id)}
                          >
                            활성화
                          </button>
                        )}
                        {r.status === 'ACTIVE' && onDeprecateRule && (
                          <button
                            className="text-xs px-2 py-0.5 rounded bg-red-50 hover:bg-red-100 text-red-700"
                            onClick={() => onDeprecateRule(r.id)}
                          >
                            비활성화
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {expansionRules.length === 0 && (
            <div className="py-6 text-center text-muted-foreground text-sm">이 그룹에 등록된 확장 규칙이 없습니다</div>
          )}
        </div>
      )}
    </div>
  );
}
