/**
 * ObjectTypeTree — 좌측 패널 트리 뷰
 *
 * ActionType 과 Policy 를 그룹별로 표시한다.
 * - ActionType: when_event 기준으로 그룹핑
 * - Policy: target_service 기준으로 그룹핑
 *
 * 클릭 시 해당 항목을 선택하고, 우측 에디터에 반영한다.
 * 추가 버튼으로 신규 생성 모드를 활성화한다.
 */

import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ChevronRight,
  ChevronDown,
  Zap,
  Shield,
  Plus,
  Search,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useDomainModelerStore } from '../store/useDomainModelerStore';
import type { ActionType, Policy } from '../types/domainModeler.types';

interface ObjectTypeTreeProps {
  /** ActionType 목록 */
  actionTypes: ActionType[];
  /** Policy 목록 */
  policies: Policy[];
  /** ActionType/Policy 목록 로딩 중 */
  loading?: boolean;
}

/** 트리 그룹의 펼침 상태를 관리하는 컴포넌트 */
const TreeGroup: React.FC<{
  label: string;
  count: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}> = ({ label, count, defaultOpen = true, children }) => {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div>
      <button
        className="flex items-center gap-1 w-full px-2 py-1.5 text-xs font-semibold
                   text-muted-foreground hover:text-foreground transition-colors"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="h-3 w-3 shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0" />
        )}
        <span className="truncate">{label}</span>
        <Badge
          variant="secondary"
          className="ml-auto text-[10px] h-4 px-1.5"
        >
          {count}
        </Badge>
      </button>
      {open && <div className="ml-3 border-l border-border/40 pl-2">{children}</div>}
    </div>
  );
};

export const ObjectTypeTree: React.FC<ObjectTypeTreeProps> = ({
  actionTypes,
  policies,
  loading = false,
}) => {
  const { t } = useTranslation();
  const {
    selectedActionType,
    selectedPolicy,
    selectActionType,
    selectPolicy,
    treeSearchQuery,
    setTreeSearchQuery,
  } = useDomainModelerStore();

  // 검색어 필터 적용
  const query = treeSearchQuery.toLowerCase();

  const filteredActionTypes = useMemo(
    () =>
      query
        ? actionTypes.filter(
            (at) =>
              at.name.toLowerCase().includes(query) ||
              at.when_event.toLowerCase().includes(query),
          )
        : actionTypes,
    [actionTypes, query],
  );

  const filteredPolicies = useMemo(
    () =>
      query
        ? policies.filter(
            (p) =>
              p.name.toLowerCase().includes(query) ||
              p.target_service.toLowerCase().includes(query),
          )
        : policies,
    [policies, query],
  );

  // ActionType 을 when_event 기준으로 그룹핑
  const actionTypeGroups = useMemo(() => {
    const groups = new Map<string, ActionType[]>();
    filteredActionTypes.forEach((at) => {
      const key = at.when_event || t('domainModeler.noEventGroup');
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(at);
    });
    return groups;
  }, [filteredActionTypes]);

  // Policy 를 target_service 기준으로 그룹핑
  const policyGroups = useMemo(() => {
    const groups = new Map<string, Policy[]>();
    filteredPolicies.forEach((p) => {
      const key = p.target_service || t('domainModeler.noServiceGroup');
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(p);
    });
    return groups;
  }, [filteredPolicies]);

  /** 새 ActionType 생성 모드 */
  const handleNewActionType = () => {
    selectActionType(null);
    // editorTarget 을 actionType 으로 설정 — store에서 null 선택 시 editorTarget 이 null 이 되므로 직접 설정
    useDomainModelerStore.setState({ editorTarget: 'actionType' });
  };

  /** 새 Policy 생성 모드 */
  const handleNewPolicy = () => {
    selectPolicy(null);
    useDomainModelerStore.setState({ editorTarget: 'policy' });
  };

  return (
    <div className="flex flex-col h-full">
      {/* 검색 바 */}
      <div className="p-2 border-b border-border/50">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            className="h-8 pl-7 text-xs"
            placeholder={t('domainModeler.search')}
            value={treeSearchQuery}
            onChange={(e) => setTreeSearchQuery(e.target.value)}
            aria-label={t('domainModeler.treeSearch')}
          />
        </div>
      </div>

      {/* 트리 본체 */}
      <div className="flex-1 overflow-y-auto px-1 py-2 space-y-3">
        {loading ? (
          <p className="text-xs text-muted-foreground text-center py-4">
            {t('domainModeler.loading')}
          </p>
        ) : (
          <>
            {/* ── ActionType 섹션 ── */}
            <div>
              <div className="flex items-center justify-between px-2 mb-1">
                <div className="flex items-center gap-1 text-xs font-bold text-foreground">
                  <Zap className="h-3.5 w-3.5 text-amber-400" />
                  ActionTypes
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={handleNewActionType}
                  aria-label={t('domainModeler.newActionTypeBtn')}
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </div>

              {actionTypeGroups.size === 0 ? (
                <p className="text-[11px] text-muted-foreground px-4 py-1 italic">
                  {query ? t('domainModeler.noSearchResults') : t('domainModeler.noActionTypes')}
                </p>
              ) : (
                Array.from(actionTypeGroups.entries()).map(([event, items]) => (
                  <TreeGroup key={`at-${event}`} label={event} count={items.length}>
                    {items.map((at) => (
                      <button
                        key={at.id}
                        className={`flex items-center gap-1.5 w-full px-2 py-1 text-xs rounded
                                    transition-colors truncate
                                    ${
                                      selectedActionType?.id === at.id
                                        ? 'bg-primary/15 text-primary font-medium'
                                        : 'text-foreground hover:bg-muted/60'
                                    }`}
                        onClick={() => selectActionType(at)}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full shrink-0 ${
                            at.enabled ? 'bg-green-500' : 'bg-gray-400'
                          }`}
                        />
                        <span className="truncate">{at.name}</span>
                      </button>
                    ))}
                  </TreeGroup>
                ))
              )}
            </div>

            {/* ── Policy 섹션 ── */}
            <div>
              <div className="flex items-center justify-between px-2 mb-1">
                <div className="flex items-center gap-1 text-xs font-bold text-foreground">
                  <Shield className="h-3.5 w-3.5 text-blue-400" />
                  Policies
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={handleNewPolicy}
                  aria-label={t('domainModeler.newPolicyBtn')}
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </div>

              {policyGroups.size === 0 ? (
                <p className="text-[11px] text-muted-foreground px-4 py-1 italic">
                  {query ? t('domainModeler.noSearchResults') : t('domainModeler.noPolicies')}
                </p>
              ) : (
                Array.from(policyGroups.entries()).map(([service, items]) => (
                  <TreeGroup
                    key={`pol-${service}`}
                    label={service}
                    count={items.length}
                  >
                    {items.map((p) => (
                      <button
                        key={p.id}
                        className={`flex items-center gap-1.5 w-full px-2 py-1 text-xs rounded
                                    transition-colors truncate
                                    ${
                                      selectedPolicy?.id === p.id
                                        ? 'bg-primary/15 text-primary font-medium'
                                        : 'text-foreground hover:bg-muted/60'
                                    }`}
                        onClick={() => selectPolicy(p)}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full shrink-0 ${
                            p.enabled ? 'bg-green-500' : 'bg-gray-400'
                          }`}
                        />
                        <span className="truncate">{p.name}</span>
                      </button>
                    ))}
                  </TreeGroup>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
