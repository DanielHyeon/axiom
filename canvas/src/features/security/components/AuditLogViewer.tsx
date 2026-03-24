/**
 * AuditLogViewer — 감사 로그 테이블 + 필터
 * KAIR AuditLogs.vue에서 이식
 * - 날짜 범위 필터, 액션/사용자/상태 필터
 * - 페이지네이션
 * - 상세 모달
 */

import React, { useState, useCallback } from 'react';
import {
  Search,
  RefreshCw,
  Loader2,
  Eye,
  X,
  AlertTriangle,
  FileText,
  ChevronLeft,
  ChevronRight,
  Calendar,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { useAuditLogs } from '../hooks/useSecurity';
import type { AuditLogEntry, AuditLogFilter, AuditLogStatus } from '../types/security';
import { useTranslation } from 'react-i18next';

// ---------------------------------------------------------------------------
// 상태 배지 스타일
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  allowed: { label: t('securityExt.decision.allowed'), className: 'bg-emerald-100 text-emerald-700' },
  denied: { label: t('securityExt.decision.denied'), className: 'bg-red-100 text-red-600' },
  rewritten: { label: t('securityExt.decision.rewritten'), className: 'bg-amber-100 text-amber-700' },
};

// ---------------------------------------------------------------------------
// 날짜/시간 포맷
// ---------------------------------------------------------------------------

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return ts;
  }
}

function formatFullTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString('ko-KR');
  } catch {
    return ts;
  }
}

// ---------------------------------------------------------------------------
// AuditLogViewer 컴포넌트
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20;

export const AuditLogViewer: React.FC = () => {
  const { t } = useTranslation();
  // 필터 상태
  const [filter, setFilter] = useState<AuditLogFilter>({
    page: 1,
    page_size: PAGE_SIZE,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // 서버 상태
  const queryFilter: AuditLogFilter = {
    ...filter,
    status: statusFilter !== 'all' ? (statusFilter as AuditLogStatus) : undefined,
    user_email: searchQuery || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  };
  const { data, isLoading, isError, error, refetch } = useAuditLogs(queryFilter);

  const logs = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = filter.page ?? 1;

  // 상세 모달 상태
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);

  // 페이지 변경
  const goToPage = useCallback(
    (page: number) => {
      setFilter((prev) => ({ ...prev, page }));
    },
    [],
  );

  // 필터 적용 (검색 시 1페이지로)
  const applySearch = useCallback(() => {
    setFilter((prev) => ({ ...prev, page: 1 }));
  }, []);

  return (
    <div className="flex flex-col gap-5">
      {/* 헤더 */}
      <div>
        <h2 className="text-lg font-semibold text-foreground">{t('securityExt.auditLog')}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('securityF.m91771f5c')}
        </p>
      </div>

      {/* 필터 바 */}
      <div className="flex flex-wrap items-center gap-3">
        {/* 사용자/키워드 검색 */}
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applySearch()}
            placeholder={t('securityExt.searchEmail')}
            className="pl-9"
          />
        </div>

        {/* 상태 필터 */}
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v);
            setFilter((prev) => ({ ...prev, page: 1 }));
          }}
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder={t('dataQualityExt.incidentCols.status')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('securityExt.allStatus')}</SelectItem>
            <SelectItem value="allowed">{t('securityExt.decision.allowed')}</SelectItem>
            <SelectItem value="denied">{t('securityExt.decision.denied')}</SelectItem>
            <SelectItem value="rewritten">{t('securityExt.decision.rewritten')}</SelectItem>
          </SelectContent>
        </Select>

        {/* 날짜 범위 */}
        <div className="flex items-center gap-1.5">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setFilter((prev) => ({ ...prev, page: 1 }));
            }}
            className="w-36 text-xs"
            aria-label={t('securityExt.startDate')}
          />
          <span className="text-muted-foreground text-sm">~</span>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setFilter((prev) => ({ ...prev, page: 1 }));
            }}
            className="w-36 text-xs"
            aria-label={t('securityExt.endDate')}
          />
        </div>

        {/* 새로고침 */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
          {t('datasourceExt.refreshBtn')}
        </Button>
      </div>

      {/* 에러 */}
      {isError && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{t('securityF.msg29ca2c85')}</span>
        </div>
      )}

      {/* 로딩 */}
      {isLoading && !isError && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-sm">{t('securityExt.loadingLogs')}</span>
        </div>
      )}

      {/* 빈 상태 */}
      {!isLoading && !isError && logs.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <FileText className="h-10 w-10" />
          <p className="font-medium">{t('securityExt.noAuditLogs')}</p>
          <span className="text-sm">{t('securityExt.noAuditLogsHint')}</span>
        </div>
      )}

      {/* 로그 테이블 */}
      {!isLoading && !isError && logs.length > 0 && (
        <>
          <div className="border border-border rounded-xl overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('securityExt.time')}</TableHead>
                  <TableHead>{t('securityExt.user')}</TableHead>
                  <TableHead>{t('securityExt.action')}</TableHead>
                  <TableHead>{t('securityExt.resourceCol')}</TableHead>
                  <TableHead>{t('securityExt.statusCol')}</TableHead>
                  <TableHead>IP</TableHead>
                  <TableHead className="w-16">{t('objectExplorerExt.detailTab')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="text-muted-foreground text-xs whitespace-nowrap">
                      {formatTimestamp(log.timestamp)}
                    </TableCell>
                    <TableCell className="font-medium text-sm">
                      {log.user_email}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {log.action}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm max-w-[200px] truncate" title={log.resource}>
                      {log.resource}
                    </TableCell>
                    <TableCell>
                      {log.status && STATUS_CONFIG[log.status] ? (
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_CONFIG[log.status].className}`}
                        >
                          {STATUS_CONFIG[log.status].label}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground font-mono">
                      {log.ip_address || '-'}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => setSelectedLog(log)}
                        aria-label={t('securityExt.viewDetail')}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* 페이지네이션 */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {t('securityF.paginationInfo', { total: total.toLocaleString(), from: (currentPage - 1) * PAGE_SIZE + 1, to: Math.min(currentPage * PAGE_SIZE, total) })}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage <= 1}
                onClick={() => goToPage(currentPage - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-foreground px-3">
                {currentPage} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage >= totalPages}
                onClick={() => goToPage(currentPage + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 상세 모달 */}
      {/* ----------------------------------------------------------------- */}
      {selectedLog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedLog(null);
          }}
          role="dialog"
          aria-modal="true"
          aria-label={t('securityExt.auditDetail')}
        >
          <div className="bg-card border border-border rounded-2xl w-[600px] max-h-[80vh] overflow-hidden shadow-2xl flex flex-col">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">{t('securityExt.auditDetail')}</h3>
              <Button variant="ghost" size="icon" onClick={() => setSelectedLog(null)}>
                <X className="h-5 w-5" />
              </Button>
            </div>
            {/* 본문 */}
            <div className="p-6 overflow-y-auto flex flex-col gap-4">
              {/* 기본 정보 */}
              <DetailRow label={t('securityExt.logId')} value={selectedLog.id} mono />
              <DetailRow label={t('securityExt.time')} value={formatFullTimestamp(selectedLog.timestamp)} />
              <DetailRow label={t('caseDashboardExt.defaultUser')} value={selectedLog.user_email} />
              <DetailRow label={t('mvExt.colActions')} value={selectedLog.action} />
              <DetailRow label={t('securityExt.resourceCol')} value={selectedLog.resource} />
              <DetailRow label={t('securityExt.ipAddress')} value={selectedLog.ip_address || '-'} mono />

              {/* 상태 */}
              {selectedLog.status && (
                <div className="flex gap-4">
                  <span className="w-24 shrink-0 text-sm font-medium text-muted-foreground">
                    {t('dataQualityExt.incidentCols.status')}
                  </span>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_CONFIG[selectedLog.status]?.className || ''}`}
                  >
                    {STATUS_CONFIG[selectedLog.status]?.label || selectedLog.status}
                  </span>
                </div>
              )}

              {/* 상세 정보 */}
              {selectedLog.details && (
                <DetailRow label={t('objectExplorerExt.detailTab')} value={selectedLog.details} />
              )}

              {/* SQL (있을 경우) */}
              {selectedLog.original_sql && (
                <div className="flex flex-col gap-2">
                  <span className="text-sm font-medium text-muted-foreground">{t('securityExt.originalSql')}</span>
                  <pre className="p-4 bg-muted/50 border border-border rounded-lg text-xs font-mono whitespace-pre-wrap break-all text-foreground">
                    {selectedLog.original_sql}
                  </pre>
                </div>
              )}

              {selectedLog.rewritten_sql && (
                <div className="flex flex-col gap-2">
                  <span className="text-sm font-medium text-muted-foreground">{t('securityExt.rewrittenSql')}</span>
                  <pre className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-xs font-mono whitespace-pre-wrap break-all text-foreground">
                    {selectedLog.rewritten_sql}
                  </pre>
                </div>
              )}

              {/* 실행 시간 */}
              {selectedLog.execution_time_ms != null && (
                <DetailRow
                  label={t('securityExt.executionTime')}
                  value={`${selectedLog.execution_time_ms}ms`}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// 상세 행 헬퍼 컴포넌트
// ---------------------------------------------------------------------------

function DetailRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex gap-4">
      <span className="w-24 shrink-0 text-sm font-medium text-muted-foreground">
        {label}
      </span>
      <span
        className={`text-sm text-foreground ${mono ? 'font-mono text-xs' : ''}`}
      >
        {value}
      </span>
    </div>
  );
}
