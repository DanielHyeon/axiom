/**
 * 별칭 규칙 워크벤치 — 별칭 그룹 + 확장 규칙 관리 UI
 *
 * 운영자가 온톨로지 용어의 별칭 그룹과 확장 규칙을 관리한다.
 * 왼쪽: 별칭 그룹 목록, 오른쪽: 선택된 그룹의 확장 규칙, 하단: 생성 폼
 */
import { useState } from 'react';
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Plus,
  Play,
  Ban,
  Search,
  Loader2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  useAliasGroups,
  useExpansionRules,
  useCreateAliasGroup,
  useCreateExpansionRule,
  useActivateRule,
  useDeprecateRule,
} from '../hooks/useSemanticCatalog';
import type { AliasGroup, ExpansionRuleType } from '../types/semantic';

/** 규칙 타입별 배지 색상 */
const RULE_TYPE_STYLE: Record<string, string> = {
  EXACT: 'bg-blue-100 text-blue-800',
  NORMALIZED_EXACT: 'bg-indigo-100 text-indigo-800',
  TOKEN_SET: 'bg-purple-100 text-purple-800',
  REGEX: 'bg-orange-100 text-orange-800',
  TIME_ALIAS: 'bg-teal-100 text-teal-800',
  ACRONYM: 'bg-cyan-100 text-cyan-800',
  NEGATIVE_RULE: 'bg-red-100 text-red-800',
};

/** 규칙 상태 배지 */
function RuleStatusBadge({ status }: { status: string }) {
  const isActive = status === 'ACTIVE';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        isActive ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'
      }`}
    >
      {isActive ? '활성' : '비활성'}
    </span>
  );
}

/** 규칙 타입 선택지 */
const RULE_TYPES: ExpansionRuleType[] = [
  'EXACT',
  'NORMALIZED_EXACT',
  'TOKEN_SET',
  'REGEX',
  'TIME_ALIAS',
  'ACRONYM',
  'NEGATIVE_RULE',
];

export function AliasRuleWorkbench() {
  // 선택된 별칭 그룹
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  // 생성 폼 열기/닫기
  const [showGroupForm, setShowGroupForm] = useState(false);
  const [showRuleForm, setShowRuleForm] = useState(false);

  // 그룹 생성 폼 상태
  const [newGroup, setNewGroup] = useState({
    group_name: '',
    canonical_term_id: '',
    domain_id: '',
    language_code: 'ko',
  });

  // 규칙 생성 폼 상태
  const [newRule, setNewRule] = useState({
    match_pattern: '',
    rule_type: 'EXACT' as ExpansionRuleType,
    boost: 1.0,
    priority: 100,
  });

  // 데이터 조회
  const { data: aliasGroups = [], isLoading: groupsLoading } = useAliasGroups();
  const { data: expansionRules = [], isLoading: rulesLoading } = useExpansionRules(
    selectedGroupId ?? undefined,
  );

  // 뮤테이션
  const createGroup = useCreateAliasGroup();
  const createRule = useCreateExpansionRule();
  const activateRule = useActivateRule();
  const deprecateRule = useDeprecateRule();

  // 선택된 그룹 객체
  const selectedGroup: AliasGroup | undefined = aliasGroups.find(
    (g) => g.id === selectedGroupId,
  );

  /** 그룹 생성 제출 */
  const handleCreateGroup = () => {
    if (!newGroup.group_name || !newGroup.canonical_term_id) return;
    createGroup.mutate(newGroup, {
      onSuccess: () => {
        setNewGroup({ group_name: '', canonical_term_id: '', domain_id: '', language_code: 'ko' });
        setShowGroupForm(false);
      },
    });
  };

  /** 규칙 생성 제출 */
  const handleCreateRule = () => {
    if (!selectedGroupId || !newRule.match_pattern) return;
    createRule.mutate(
      { alias_group_id: selectedGroupId, ...newRule },
      {
        onSuccess: () => {
          setNewRule({ match_pattern: '', rule_type: 'EXACT', boost: 1.0, priority: 100 });
          setShowRuleForm(false);
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-indigo-600" />
        <h2 className="text-lg font-semibold">별칭 규칙 워크벤치</h2>
      </div>

      {/* 2열 레이아웃: 그룹 목록(40%) + 규칙 목록(60%) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* ── 왼쪽: 별칭 그룹 목록 ── */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-sm text-muted-foreground">별칭 그룹</h3>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowGroupForm((v) => !v)}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              그룹 추가
            </Button>
          </div>

          {/* 그룹 목록 테이블 */}
          <div className="rounded-lg border">
            {groupsLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                로딩 중...
              </div>
            ) : aliasGroups.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground text-sm">
                등록된 별칭 그룹이 없습니다
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-3 py-2 text-left font-medium">그룹명</th>
                    <th className="px-3 py-2 text-left font-medium">정규 용어</th>
                    <th className="px-3 py-2 text-left font-medium">도메인</th>
                    <th className="px-3 py-2 text-center font-medium">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {aliasGroups.map((group) => {
                    const isSelected = selectedGroupId === group.id;
                    return (
                      <tr
                        key={group.id}
                        className={`border-b cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-indigo-50 hover:bg-indigo-100'
                            : 'hover:bg-muted/30'
                        }`}
                        onClick={() => setSelectedGroupId(isSelected ? null : group.id)}
                      >
                        <td className="px-3 py-2 font-medium">
                          <div className="flex items-center gap-1.5">
                            {isSelected ? (
                              <ChevronDown className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                            ) : (
                              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                            )}
                            {group.group_name}
                          </div>
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                          {group.canonical_term_id}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground text-xs">
                          {group.domain_id || '—'}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <RuleStatusBadge status={group.status} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* 그룹 생성 폼 (접이식) */}
          {showGroupForm && (
            <div className="rounded-lg border p-4 bg-muted/20 space-y-3">
              <h4 className="text-sm font-medium">새 별칭 그룹</h4>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="그룹명"
                  value={newGroup.group_name}
                  onChange={(e) =>
                    setNewGroup((v) => ({ ...v, group_name: e.target.value }))
                  }
                />
                <Input
                  placeholder="정규 용어 ID"
                  value={newGroup.canonical_term_id}
                  onChange={(e) =>
                    setNewGroup((v) => ({ ...v, canonical_term_id: e.target.value }))
                  }
                />
                <Input
                  placeholder="도메인 ID"
                  value={newGroup.domain_id}
                  onChange={(e) =>
                    setNewGroup((v) => ({ ...v, domain_id: e.target.value }))
                  }
                />
                <Input
                  placeholder="언어 코드 (ko)"
                  value={newGroup.language_code}
                  onChange={(e) =>
                    setNewGroup((v) => ({ ...v, language_code: e.target.value }))
                  }
                />
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleCreateGroup}
                  disabled={createGroup.isPending || !newGroup.group_name}
                >
                  {createGroup.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />}
                  등록
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowGroupForm(false)}
                >
                  취소
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* ── 오른쪽: 확장 규칙 목록 ── */}
        <div className="lg:col-span-3 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-sm text-muted-foreground">
              {selectedGroup ? (
                <>
                  확장 규칙 —{' '}
                  <span className="text-foreground">{selectedGroup.group_name}</span>
                </>
              ) : (
                '확장 규칙 (그룹을 선택하세요)'
              )}
            </h3>
            {selectedGroupId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowRuleForm((v) => !v)}
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                규칙 추가
              </Button>
            )}
          </div>

          {/* 규칙 테이블 */}
          <div className="rounded-lg border">
            {!selectedGroupId ? (
              <div className="py-12 text-center text-muted-foreground text-sm">
                왼쪽에서 별칭 그룹을 선택하면 확장 규칙이 표시됩니다
              </div>
            ) : rulesLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                로딩 중...
              </div>
            ) : expansionRules.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground text-sm">
                등록된 확장 규칙이 없습니다
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-3 py-2 text-left font-medium">매치 패턴</th>
                    <th className="px-3 py-2 text-left font-medium">규칙 타입</th>
                    <th className="px-3 py-2 text-center font-medium">부스트</th>
                    <th className="px-3 py-2 text-center font-medium">우선순위</th>
                    <th className="px-3 py-2 text-center font-medium">상태</th>
                    <th className="px-3 py-2 text-center font-medium">액션</th>
                  </tr>
                </thead>
                <tbody>
                  {expansionRules.map((rule) => (
                    <tr key={rule.id} className="border-b hover:bg-muted/30">
                      <td className="px-3 py-2">
                        <code className="text-xs bg-slate-100 rounded px-1.5 py-0.5">
                          {rule.match_pattern}
                        </code>
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${
                            RULE_TYPE_STYLE[rule.rule_type] ?? 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {rule.rule_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center tabular-nums font-mono text-xs">
                        {rule.boost.toFixed(1)}
                      </td>
                      <td className="px-3 py-2 text-center tabular-nums font-mono text-xs">
                        {rule.priority}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <RuleStatusBadge status={rule.status} />
                      </td>
                      <td className="px-3 py-2 text-center">
                        <div className="flex items-center justify-center gap-1">
                          {rule.status === 'DEPRECATED' && (
                            <button
                              className="p-1 rounded hover:bg-green-50"
                              title="활성화"
                              onClick={() => activateRule.mutate(rule.id)}
                              disabled={activateRule.isPending}
                            >
                              <Play className="h-3.5 w-3.5 text-green-600" />
                            </button>
                          )}
                          {rule.status === 'ACTIVE' && (
                            <button
                              className="p-1 rounded hover:bg-red-50"
                              title="비활성화"
                              onClick={() => deprecateRule.mutate(rule.id)}
                              disabled={deprecateRule.isPending}
                            >
                              <Ban className="h-3.5 w-3.5 text-red-500" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* 규칙 생성 폼 (접이식) */}
          {showRuleForm && selectedGroupId && (
            <div className="rounded-lg border p-4 bg-muted/20 space-y-3">
              <h4 className="text-sm font-medium">새 확장 규칙</h4>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="매치 패턴"
                  value={newRule.match_pattern}
                  onChange={(e) =>
                    setNewRule((v) => ({ ...v, match_pattern: e.target.value }))
                  }
                />
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={newRule.rule_type}
                  onChange={(e) =>
                    setNewRule((v) => ({
                      ...v,
                      rule_type: e.target.value as ExpansionRuleType,
                    }))
                  }
                >
                  {RULE_TYPES.map((rt) => (
                    <option key={rt} value={rt}>
                      {rt}
                    </option>
                  ))}
                </select>
                <Input
                  type="number"
                  step="0.1"
                  placeholder="부스트 (1.0)"
                  value={newRule.boost}
                  onChange={(e) =>
                    setNewRule((v) => ({ ...v, boost: parseFloat(e.target.value) || 1.0 }))
                  }
                />
                <Input
                  type="number"
                  placeholder="우선순위 (100)"
                  value={newRule.priority}
                  onChange={(e) =>
                    setNewRule((v) => ({
                      ...v,
                      priority: parseInt(e.target.value, 10) || 100,
                    }))
                  }
                />
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleCreateRule}
                  disabled={createRule.isPending || !newRule.match_pattern}
                >
                  {createRule.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />}
                  등록
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowRuleForm(false)}
                >
                  취소
                </Button>
              </div>
            </div>
          )}

          {/* 테스트 플레이스홀더 */}
          <div className="rounded-lg border border-dashed p-4 text-center text-muted-foreground">
            <Search className="h-5 w-5 mx-auto mb-2 opacity-50" />
            <p className="text-sm">질문 테스트 기능 (예정)</p>
            <p className="text-xs mt-1">
              질문을 입력하면 현재 규칙에 따른 별칭 확장 결과를 미리 볼 수 있습니다
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
