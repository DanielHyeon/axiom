/**
 * TablePermissions — 테이블별 접근 권한 매트릭스
 * KAIR TablePermissions.vue에서 이식 (간소화)
 * - 스키마.테이블 목록을 행으로, 역할을 열로 배치
 * - 읽기/쓰기 체크박스 매트릭스
 */

import React, { useState } from 'react';
import {
  Database,
  RefreshCw,
  Loader2,
  AlertTriangle,
  ShieldCheck,
  Table2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useTablePermissions, useUpdateTablePermission } from '../hooks/useSecurity';
import type { TablePermission } from '../types/security';

// ---------------------------------------------------------------------------
// 역할 라벨 (한글)
// ---------------------------------------------------------------------------

const ROLE_LABEL: Record<string, string> = {
  admin: '관리자',
  manager: '매니저',
  analyst: '분석가',
  engineer: '엔지니어',
  staff: '직원',
  viewer: '뷰어',
};

// ---------------------------------------------------------------------------
// TablePermissions 컴포넌트
// ---------------------------------------------------------------------------

export const TablePermissions: React.FC = () => {
  const {
    data: permissions = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useTablePermissions();
  const updateMutation = useUpdateTablePermission();

  const [searchQuery, setSearchQuery] = useState('');

  // 모든 역할 이름 추출 (테이블에 사용된 역할 합집합)
  const allRoles = React.useMemo(() => {
    const roleSet = new Set<string>();
    permissions.forEach((tp) => {
      Object.keys(tp.roles).forEach((r) => roleSet.add(r));
    });
    // 기본 역할이 없으면 추가
    ['admin', 'manager', 'analyst', 'engineer', 'staff', 'viewer'].forEach((r) =>
      roleSet.add(r),
    );
    return Array.from(roleSet).sort();
  }, [permissions]);

  // 검색 필터
  const filteredPermissions = permissions.filter((tp) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      tp.table_name.toLowerCase().includes(q) ||
      tp.schema.toLowerCase().includes(q)
    );
  });

  // 체크박스 토글 핸들러
  const handleToggle = (
    tp: TablePermission,
    roleName: string,
    field: 'read' | 'write',
  ) => {
    const currentPerms = tp.roles[roleName] || { read: false, write: false };
    const newPerms = { ...currentPerms, [field]: !currentPerms[field] };
    // write가 켜지면 read도 자동으로 켜기
    if (field === 'write' && newPerms.write) {
      newPerms.read = true;
    }
    // read가 꺼지면 write도 자동으로 끄기
    if (field === 'read' && !newPerms.read) {
      newPerms.write = false;
    }

    updateMutation.mutate({
      tableName: tp.table_name,
      schema: tp.schema,
      roles: { ...tp.roles, [roleName]: newPerms },
    });
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">테이블 권한</h2>
          <p className="text-sm text-muted-foreground mt-1">
            스키마/테이블별 역할 접근 권한을 관리합니다. 체크박스로 읽기/쓰기 권한을 제어합니다.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
          새로고침
        </Button>
      </div>

      {/* 에러 */}
      {isError && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>테이블 권한 데이터를 불러오는 데 실패했습니다. {(error as Error)?.message}</span>
        </div>
      )}

      {/* 로딩 */}
      {isLoading && !isError && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-sm">테이블 권한 로딩 중...</span>
        </div>
      )}

      {/* 빈 상태 */}
      {!isLoading && !isError && permissions.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <Database className="h-10 w-10" />
          <p className="font-medium">등록된 테이블 권한이 없습니다</p>
          <span className="text-sm">데이터소스를 연결하면 테이블이 자동으로 표시됩니다</span>
        </div>
      )}

      {/* 권한 매트릭스 */}
      {!isLoading && !isError && permissions.length > 0 && (
        <>
          {/* 검색 */}
          <div className="relative w-80">
            <Database className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="테이블 또는 스키마 검색..."
              className="pl-9"
            />
          </div>

          {/* 매트릭스 테이블 */}
          <div className="border border-border rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 border-b border-border">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider sticky left-0 bg-muted/50 z-10 min-w-[200px]">
                      스키마 / 테이블
                    </th>
                    {allRoles.map((role) => (
                      <th
                        key={role}
                        className="text-center px-2 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                        colSpan={2}
                      >
                        {ROLE_LABEL[role] || role}
                      </th>
                    ))}
                  </tr>
                  {/* 읽기/쓰기 서브 헤더 */}
                  <tr className="bg-muted/30 border-b border-border">
                    <th className="sticky left-0 bg-muted/30 z-10" />
                    {allRoles.map((role) => (
                      <React.Fragment key={role}>
                        <th className="text-center px-2 py-1.5 text-[10px] font-medium text-muted-foreground">
                          R
                        </th>
                        <th className="text-center px-2 py-1.5 text-[10px] font-medium text-muted-foreground">
                          W
                        </th>
                      </React.Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredPermissions.map((tp) => (
                    <tr
                      key={`${tp.schema}.${tp.table_name}`}
                      className="border-b border-border/50 last:border-0 hover:bg-muted/20"
                    >
                      {/* 테이블 이름 */}
                      <td className="px-4 py-2.5 sticky left-0 bg-card z-10">
                        <div className="flex items-center gap-2">
                          <Table2 className="h-4 w-4 text-emerald-500 shrink-0" />
                          <div>
                            <span className="text-foreground font-medium">
                              {tp.table_name}
                            </span>
                            <span className="text-muted-foreground text-xs ml-1.5">
                              {tp.schema}
                            </span>
                          </div>
                        </div>
                      </td>
                      {/* 역할별 체크박스 */}
                      {allRoles.map((role) => {
                        const perms = tp.roles[role] || { read: false, write: false };
                        return (
                          <React.Fragment key={role}>
                            <td className="text-center px-2 py-2.5">
                              <Checkbox
                                checked={perms.read}
                                onCheckedChange={() => handleToggle(tp, role, 'read')}
                                aria-label={`${tp.table_name} ${role} 읽기`}
                              />
                            </td>
                            <td className="text-center px-2 py-2.5">
                              <Checkbox
                                checked={perms.write}
                                onCheckedChange={() => handleToggle(tp, role, 'write')}
                                aria-label={`${tp.table_name} ${role} 쓰기`}
                              />
                            </td>
                          </React.Fragment>
                        );
                      })}
                    </tr>
                  ))}
                  {filteredPermissions.length === 0 && (
                    <tr>
                      <td
                        colSpan={1 + allRoles.length * 2}
                        className="text-center py-8 text-muted-foreground"
                      >
                        검색 결과가 없습니다
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* 범례 */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="font-medium">범례:</span>
            <span>R = 읽기 (Read)</span>
            <span>W = 쓰기 (Write)</span>
            <span className="text-amber-600">
              * 쓰기 활성화 시 읽기가 자동으로 활성화됩니다
            </span>
          </div>
        </>
      )}
    </div>
  );
};
