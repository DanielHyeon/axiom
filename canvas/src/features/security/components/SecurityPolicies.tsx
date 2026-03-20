/**
 * SecurityPolicies — 보안 정책 설정 (읽기 전용 뷰)
 * KAIR SecurityPolicies.vue에서 이식
 * - 보안 정책 카드 목록
 * - JSON 규칙 미리보기
 * - 활성/비활성 토글
 *
 * 참고: 백엔드 API가 구현되면 실제 CRUD로 전환 예정.
 *       현재는 Mock 데이터로 UI 구조만 제공.
 */

import React, { useState } from 'react';
import { Shield, Pencil, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { SecurityPolicy, SecurityPolicyType } from '../types/security';

// ---------------------------------------------------------------------------
// 정책 타입 라벨 + 아이콘
// ---------------------------------------------------------------------------

const POLICY_TYPE_CONFIG: Record<SecurityPolicyType, { label: string; color: string }> = {
  query_limit: { label: '쿼리 제한', color: 'bg-blue-100 text-blue-700' },
  column_mask: { label: '컬럼 마스킹', color: 'bg-purple-100 text-purple-700' },
  column_filter: { label: '컬럼 필터', color: 'bg-red-100 text-red-600' },
  query_rewrite: { label: '쿼리 변환', color: 'bg-amber-100 text-amber-700' },
  rate_limit: { label: '속도 제한', color: 'bg-emerald-100 text-emerald-700' },
};

// ---------------------------------------------------------------------------
// Mock 데이터 — 백엔드 구현 전 UI 검증용
// ---------------------------------------------------------------------------

const MOCK_POLICIES: SecurityPolicy[] = [
  {
    name: 'default_limit',
    policy_type: 'query_limit',
    description: '기본 SELECT 결과 행 수 제한',
    rules_json: JSON.stringify({ max_rows: 1000, enforce_limit: true }, null, 2),
    priority: 100,
    is_active: true,
  },
  {
    name: 'pii_protection',
    policy_type: 'column_mask',
    description: '개인정보(PII) 컬럼 마스킹',
    rules_json: JSON.stringify(
      { masked_columns: ['ssn', 'phone', 'email', 'address'], mask_pattern: '***', except_roles: ['admin'] },
      null,
      2,
    ),
    priority: 90,
    is_active: true,
  },
  {
    name: 'salary_restriction',
    policy_type: 'column_filter',
    description: '급여 정보 접근 제한',
    rules_json: JSON.stringify(
      { restricted_columns: ['salary', 'bonus', 'commission'], allowed_roles: ['admin', 'hr_manager'] },
      null,
      2,
    ),
    priority: 85,
    is_active: true,
  },
  {
    name: 'rate_limit',
    policy_type: 'rate_limit',
    description: '쿼리 실행 속도 제한',
    rules_json: JSON.stringify(
      { max_queries_per_minute: 100, max_concurrent: 5, except_roles: ['admin'] },
      null,
      2,
    ),
    priority: 70,
    is_active: true,
  },
];

// ---------------------------------------------------------------------------
// SecurityPolicies 컴포넌트
// ---------------------------------------------------------------------------

export const SecurityPolicies: React.FC = () => {
  const [policies, setPolicies] = useState<SecurityPolicy[]>(MOCK_POLICIES);
  const [editingPolicy, setEditingPolicy] = useState<SecurityPolicy | null>(null);
  const [editJson, setEditJson] = useState('');

  // 정책 활성 토글
  const toggleActive = (name: string) => {
    setPolicies((prev) =>
      prev.map((p) => (p.name === name ? { ...p, is_active: !p.is_active } : p)),
    );
  };

  // 편집 다이얼로그 열기
  const openEdit = (policy: SecurityPolicy) => {
    setEditingPolicy(policy);
    setEditJson(policy.rules_json);
  };

  // 편집 저장
  const saveEdit = () => {
    if (!editingPolicy) return;
    // JSON 유효성 검증
    try {
      JSON.parse(editJson);
    } catch {
      alert('유효한 JSON 형식이 아닙니다.');
      return;
    }
    setPolicies((prev) =>
      prev.map((p) =>
        p.name === editingPolicy.name ? { ...p, rules_json: editJson } : p,
      ),
    );
    setEditingPolicy(null);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 헤더 */}
      <div>
        <h2 className="text-lg font-semibold text-foreground">보안 정책</h2>
        <p className="text-sm text-muted-foreground mt-1">
          SQL 쿼리에 적용되는 보안 정책을 관리합니다
        </p>
      </div>

      {/* 안내 배너 */}
      <div className="flex items-center gap-2 p-3 rounded-lg bg-primary/5 border border-primary/20 text-sm text-muted-foreground">
        <Shield className="h-4 w-4 text-primary shrink-0" />
        <span>
          보안 정책은 Oracle 서비스의 SQL Guard에 의해 쿼리 실행 시 자동 적용됩니다.
          백엔드 API 연동 전까지 UI 미리보기로 제공됩니다.
        </span>
      </div>

      {/* 정책 카드 */}
      <div className="flex flex-col gap-4">
        {policies.map((policy) => {
          const typeConfig = POLICY_TYPE_CONFIG[policy.policy_type];
          return (
            <div
              key={policy.name}
              className={`border border-border rounded-xl p-5 bg-card transition-all hover:border-primary/40 ${
                !policy.is_active ? 'opacity-60' : ''
              }`}
            >
              {/* 카드 헤더 */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-muted/50 flex items-center justify-center">
                    <Shield className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground font-mono text-sm">
                      {policy.name}
                    </h3>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${typeConfig.color}`}>
                      {typeConfig.label}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {/* 활성/비활성 토글 */}
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={policy.is_active}
                      onChange={() => toggleActive(policy.name)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-muted rounded-full peer peer-checked:bg-primary transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full" />
                  </label>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => openEdit(policy)}
                    aria-label="정책 수정"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {/* 설명 */}
              <p className="text-sm text-muted-foreground mb-3">{policy.description}</p>

              {/* 메타 */}
              <div className="flex items-center gap-3 mb-3 text-xs">
                <span className="text-muted-foreground">우선순위: {policy.priority}</span>
                <Badge
                  variant={policy.is_active ? 'default' : 'secondary'}
                  className="text-[10px]"
                >
                  {policy.is_active ? '활성' : '비활성'}
                </Badge>
              </div>

              {/* JSON 규칙 미리보기 */}
              <pre className="p-3 bg-muted/30 border border-border rounded-lg text-xs font-mono text-muted-foreground overflow-x-auto">
                {policy.rules_json}
              </pre>
            </div>
          );
        })}
      </div>

      {/* 편집 다이얼로그 */}
      {editingPolicy && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={(e) => {
            if (e.target === e.currentTarget) setEditingPolicy(null);
          }}
          role="dialog"
          aria-modal="true"
          aria-label="보안 정책 수정"
        >
          <div className="bg-card border border-border rounded-2xl w-[600px] max-h-[90vh] overflow-hidden shadow-2xl flex flex-col">
            <div className="flex items-center justify-between px-6 py-5 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">
                {editingPolicy.name} 정책 수정
              </h3>
              <Button variant="ghost" size="icon" onClick={() => setEditingPolicy(null)}>
                <X className="h-5 w-5" />
              </Button>
            </div>
            <div className="p-6 flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-muted-foreground">
                  정책 규칙 (JSON)
                </label>
                <textarea
                  value={editJson}
                  onChange={(e) => setEditJson(e.target.value)}
                  rows={12}
                  className="w-full p-3 border border-border rounded-lg bg-background text-foreground font-mono text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/30">
              <Button variant="outline" onClick={() => setEditingPolicy(null)}>
                취소
              </Button>
              <Button onClick={saveEdit}>저장</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
