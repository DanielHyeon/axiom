/**
 * PageShell — 페이지 레이아웃 통일 래퍼.
 * Phase 5: 모든 페이지가 동일한 패딩/제목/반응형 구조를 사용한다.
 *
 * 사용법:
 *   <PageShell title="문서 관리" subtitle="HITL 워크플로">
 *     <MyContent />
 *   </PageShell>
 */

import { cn } from '@/lib/utils';

interface PageShellProps {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  maxWidth?: boolean;
  className?: string;
  children: React.ReactNode;
}

export function PageShell({
  title,
  subtitle,
  actions,
  maxWidth = false,
  className,
  children,
}: PageShellProps) {
  return (
    <div
      className={cn(
        'flex flex-col h-full overflow-auto',
        'px-4 sm:px-8 lg:px-12 py-4 sm:py-8',
        maxWidth && 'max-w-7xl mx-auto',
        className,
      )}
    >
      {title && (
        <div className="flex items-start justify-between mb-6 shrink-0">
          <div>
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-foreground">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
