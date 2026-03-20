// 공통 로딩 스피너 — 접근성 role="status" + aria-label 포함
import { Loader2 } from 'lucide-react';

export function LoadingSpinner({
  size = 'md',
  label,
}: {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}) {
  const sizeClass = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' }[size];
  return (
    <div className="flex items-center gap-2" role="status" aria-label={label || '로딩 중'}>
      <Loader2 className={`${sizeClass} animate-spin text-gray-400`} />
      {label && <span className="text-sm text-gray-500">{label}</span>}
    </div>
  );
}
