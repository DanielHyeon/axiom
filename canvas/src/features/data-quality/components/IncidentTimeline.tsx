/**
 * IncidentTimeline — 인시던트 목록 테이블
 * KAIR IncidentManager.vue를 이식 — 필터링, 상태 뱃지, 담당자 표시
 */
import { useMemo, useState } from 'react';
import { User } from 'lucide-react';
import { useDQIncidents, useUpdateIncident } from '../hooks/useDQMetrics';
import type { DQIncident, IncidentStatus } from '../types/data-quality';

// 날짜 범위 옵션
const DATE_RANGES = [
  { label: '최근 7일', value: 7 },
  { label: '최근 30일', value: 30 },
  { label: '최근 90일', value: 90 },
  { label: '전체', value: 365 },
];

export function IncidentTimeline() {
  const { data: incidents, isLoading } = useDQIncidents();
  const updateIncident = useUpdateIncident();
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | ''>('');
  const [dateRange, setDateRange] = useState(30);

  // 필터링된 인시던트
  const filtered = useMemo(() => {
    if (!incidents) return [];
    let result = [...incidents];

    if (statusFilter) {
      result = result.filter((i) => i.status === statusFilter);
    }

    // 날짜 범위 필터
    const cutoff = new Date(Date.now() - dateRange * 86400000);
    result = result.filter((i) => new Date(i.detectedAt) >= cutoff);

    return result;
  }, [incidents, statusFilter, dateRange]);

  // 상태 뱃지 스타일
  const statusStyles: Record<string, string> = {
    open: 'bg-purple-50 text-purple-700 dark:bg-purple-500/15 dark:text-purple-400',
    acknowledged: 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400',
    resolved: 'bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-400',
  };

  // 상태 전환
  const handleStatusChange = (incident: DQIncident, newStatus: IncidentStatus) => {
    updateIncident.mutate({ id: incident.id, status: newStatus });
  };

  if (isLoading) {
    return <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">인시던트 로딩 중...</div>;
  }

  return (
    <div className="flex flex-col gap-4">
      {/* 필터 바 */}
      <div className="flex items-center gap-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | '')}
          className="px-3 py-2 bg-card border border-border rounded-md text-sm text-foreground focus:outline-none focus:border-primary"
        >
          <option value="">전체 상태</option>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>

        <div className="flex-1" />

        <select
          value={dateRange}
          onChange={(e) => setDateRange(Number(e.target.value))}
          className="px-3 py-2 bg-card border border-border rounded-md text-sm text-foreground focus:outline-none focus:border-primary"
        >
          {DATE_RANGES.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
      </div>

      {/* 인시던트 테이블 */}
      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-muted/50">
              <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase">테스트 케이스</th>
              <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase">테이블</th>
              <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase">감지 시간</th>
              <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase">상태</th>
              <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase">심각도</th>
              <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase">실패 행</th>
              <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase">담당자</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-sm text-muted-foreground">
                  인시던트가 없습니다.
                </td>
              </tr>
            ) : (
              filtered.map((inc) => (
                <tr key={inc.id} className="border-b border-border hover:bg-muted/30 transition-colors">
                  <td className="px-5 py-3">
                    <span className="text-sm text-primary hover:underline cursor-pointer">{inc.ruleName}</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-sm text-primary hover:underline cursor-pointer">{inc.tableName}</span>
                  </td>
                  <td className="px-5 py-3 text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(inc.detectedAt).toLocaleString('ko-KR')}
                  </td>
                  <td className="px-5 py-3">
                    <select
                      value={inc.status}
                      onChange={(e) => handleStatusChange(inc, e.target.value as IncidentStatus)}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium border-none cursor-pointer ${statusStyles[inc.status] ?? ''}`}
                    >
                      <option value="open">Open</option>
                      <option value="acknowledged">Acknowledged</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </td>
                  <td className="px-5 py-3">
                    <SeverityBadge severity={inc.severity} />
                  </td>
                  <td className="px-5 py-3 text-sm text-muted-foreground">{inc.failedRows}</td>
                  <td className="px-5 py-3">
                    {inc.assignee ? (
                      <span className="text-sm text-foreground">{inc.assignee}</span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <User size={12} />
                        미지정
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    critical: 'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-400 border-red-200',
    warning: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-400 border-yellow-200',
    info: 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400 border-blue-200',
  };
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-medium border ${styles[severity] ?? styles.info}`}>
      {severity}
    </span>
  );
}
