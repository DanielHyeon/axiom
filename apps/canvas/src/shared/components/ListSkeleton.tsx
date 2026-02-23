interface ListSkeletonProps {
  rows?: number;
  className?: string;
}

function SkeletonBar({ className = '' }: { className?: string }) {
  return (
    <div
      className={`h-4 rounded bg-secondary animate-pulse ${className}`}
      aria-hidden
    />
  );
}

export function ListSkeleton({ rows = 5, className = '' }: ListSkeletonProps) {
  return (
    <div className={`space-y-3 ${className}`} aria-busy="true" aria-label="로딩 중">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-3 rounded-lg border border-border bg-card">
          <SkeletonBar className="w-8 h-8 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <SkeletonBar className="w-1/3" />
            <SkeletonBar className="w-1/4" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function TableRowsSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="로딩 중">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 py-3 border-b border-border">
          <div className="h-4 w-24 rounded bg-secondary animate-pulse" />
          <div className="h-4 flex-1 max-w-[200px] rounded bg-secondary animate-pulse" />
          <div className="h-4 w-20 rounded bg-secondary animate-pulse" />
          <div className="h-4 w-24 rounded bg-secondary animate-pulse" />
        </div>
      ))}
    </div>
  );
}

export function CardGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true" aria-label="로딩 중">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="p-4 rounded-lg border border-border bg-card">
          <div className="h-4 w-1/2 rounded bg-secondary animate-pulse mb-3" />
          <div className="h-8 w-16 rounded bg-secondary animate-pulse" />
        </div>
      ))}
    </div>
  );
}
